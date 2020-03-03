# -*- coding:utf-8 -*-

# Copyright © 2017 Kiri Choi
# Based on Spyder by Spyder Project Contributors and
# AutoPEP8 plugin by Joseph Martinot-Lagarde
# Licensed under the terms of the MIT License

"""teImport Plugin"""

from __future__ import print_function, division

import os, time
import re, functools
import zipfile
import tempfile, shutil, errno
from xml.etree import ElementTree
from spyder.config.base import get_translation
from spyder.config.utils import (get_filter, get_edit_filters, 
                                 get_edit_filetypes)
from spyder.plugins import SpyderPluginMixin, SpyderDockWidget
from spyder.py3compat import getcwd, is_text_string, to_text_string
from qtpy.QtWidgets import QApplication, QMessageBox, QMenu, QAction
from qtpy.compat import getopenfilenames, from_qvariant
from spyder.utils import encoding, sourcecode
from spyder.utils.qthelpers import create_action, add_actions
from spyder.widgets.sourcecode.codeeditor import CodeEditor

try:
    import tellurium as te
except ImportError:
    raise Exception("Cannot find Tellurium. Please install Tellurium scripts first")

try:
    import phrasedml as pl
except ImportError:
    raise Exception("Cannot find PhrasedML. Please install PhrasedML package first")

_ = get_translation("teImport", dirname="spyder_teimport")

class teImport(SpyderPluginMixin):
    """teImport script"""
    CONF_SECTION = 'teImport'
    CONFIGWIDGET_CLASS = None
    
    def __init__(self, main):
        super(teImport, self).__init__(main)
        self.dockwidget = SpyderDockWidget(self.get_plugin_title(), main)
        self.dockwidget.hide()
        
    #------ SpyderPluginWidget API --------------------------------------------
    def get_plugin_title(self):
        """Return widget title"""
        return _("Import COMBINE and SED-ML")
    
    def register_plugin(self):
        """Register plugin in Spyder's main window"""
        c2p_act = create_action(self.main, _("Import COMBINE as Python"),
                                   triggered=self.run_Import)
        c2p_act.triggered.connect(functools.partial(self.run_Import, 'c2p'))
        c2pwp_act = create_action(self.main, _("Import COMBINE as PhrasedML"),
                                   triggered=self.run_Import)
        c2pwp_act.triggered.connect(functools.partial(self.run_Import, 'c2pwp'))
        s2p_act = create_action(self.main, _("Import SED-ML as Python"),
                                   triggered=self.run_Import)
        s2p_act.triggered.connect(functools.partial(self.run_Import, 's2p'))
        s2pwp_act = create_action(self.main, _("Import SED-ML as PhrasedML"),
                                   triggered=self.run_Import)
        s2pwp_act.triggered.connect(functools.partial(self.run_Import, 's2pwp'))

        for item in self.main.file_menu_actions:
            try:
                menu_title = item.title()
            except AttributeError:
                pass
            else:
                if not is_text_string(menu_title): # string is a QString
                    menu_title = to_text_string(menu_title.toUtf8)
                if item.title() == str("Import"):
                    item.addAction(c2p_act, c2pwp_act, s2p_act, s2pwp_act)
        all_actions = (None, c2p_act, c2pwp_act, s2p_act, s2pwp_act)
        import_menu = QMenu(_("Import"))
        add_actions(import_menu, all_actions)
        self.main.file_menu_actions.insert(6, import_menu)

    def on_first_registration(self):
        """Action to be performed on first plugin registration"""
        self.main.tabify_plugins(self.main.help, self)
        self.dockwidget.hide()        
        
    def closing_plugin(self, cancelable=False):
        """Perform actions before parent main window is closed"""
        return True
            
    def apply_plugin_settings(self, options):
        """Apply configuration file's plugin settings"""
        pass
        
    # --- Public API ----------------------------------------------------------
    def run_Import(self, action):
        """Prompt user to load a COMBINE archive or SED-ML file and translates it"""
        if action == 'c2p' or action == 'c2pwp' or action == 's2p' or action == 's2pwp':
            editorwindow = None #Used in editor.load
            processevents = True  #Used in editor.load
            goto = None
            word = ''
            
            editor = self.main.editor
            editor0 = editor.get_current_editor()
            if editor0 is not None:
                position0 = editor0.get_position('cursor')
                filename0 = editor.get_current_filename()
            else:
                position0, filename0 = None, None
            # Recent files action
            raction = editor.sender()
            if isinstance(raction, QAction):
                filenames = from_qvariant(raction.data(), to_text_string)
            if not filenames:
                basedir = getcwd()
                if editor.edit_filetypes is None:
                    editor.edit_filetypes = get_edit_filetypes()
                if editor.edit_filters is None:
                    editor.edit_filters = get_edit_filters()
    
                c_fname = editor.get_current_filename()
                if c_fname is not None and c_fname != editor.TEMPFILE_PATH:
                    basedir = os.path.dirname(c_fname)
                editor.redirect_stdio.emit(False)
                parent_widget = editor.get_current_editorstack()
                if filename0 is not None:
                    selectedfilter = get_filter(editor.edit_filetypes,
                                                os.path.splitext(filename0)[1])
                else:
                    selectedfilter = ''
                if action == 'c2p' or action == 'c2pwp':
                    filters = 'Combine archives (*.zip *.omex);;All files (*.*)'
                    filenames, _selfilter = getopenfilenames(parent_widget,
                                             _("Open combine archive"), basedir, filters,
                                             selectedfilter=selectedfilter)
                else:
                    filters = 'SED-ML files (*.sedml *.xml);;All files (*.*)'
                    filenames, _selfilter = getopenfilenames(parent_widget,
                                             _("Open SED-ML file"), basedir, filters,
                                             selectedfilter=selectedfilter)
                editor.redirect_stdio.emit(True)
                if filenames:
                    filenames = [os.path.normpath(fname) for fname in filenames]
                else:
                    return
            
            focus_widget = QApplication.focusWidget()
            if editor.dockwidget and not editor.ismaximized and\
               (not editor.dockwidget.isAncestorOf(focus_widget)\
                and not isinstance(focus_widget, CodeEditor)):
                editor.dockwidget.setVisible(True)
                editor.dockwidget.setFocus()
                editor.dockwidget.raise_()
            
            def _convert(fname):
                fname = os.path.abspath(encoding.to_unicode_from_fs(fname))
                if os.name == 'nt' and len(fname) >= 2 and fname[1] == ':':
                    fname = fname[0].upper()+fname[1:]
                return fname
    
            if hasattr(filenames, 'replaceInStrings'):
                # This is a QStringList instance (PyQt API #1), converting to list:
                filenames = list(filenames)
            if not isinstance(filenames, list):
                filenames = [_convert(filenames)]
            else:
                filenames = [_convert(fname) for fname in list(filenames)]
            
            if isinstance(goto, int):
                goto = [goto]
            elif goto is not None and len(goto) != len(filenames):
                goto = None
            
            for index, filename in enumerate(filenames):
                if action == 'c2p' or action == 'c2pwp':
                    p = re.compile( '(.zip$|.omex$)')
                    pythonfile = p.sub( '.py', filename)
                    if (pythonfile == filename):
                        pythonfile = filename + ".py"
                else:
                    p = re.compile( '(.xml$|.sedml$)')
                    if action == 's2p':
                        pythonfile = p.sub( '_sedml.py', filename)
                        if (pythonfile == filename):
                            pythonfile = filename + "_sedml.py"
                    else:
                        pythonfile = p.sub( '_phrasedml.py', filename)
                        if (pythonfile == filename):
                            pythonfile = filename + "_phrasedml.py"
                current_editor = editor.set_current_filename(pythonfile, editorwindow)
                if current_editor is None:
                    # -- Not a valid filename:
                    if not os.path.isfile(filename):
                        continue
                    # --
                    current_es = editor.get_current_editorstack(editorwindow)
    
                    # Creating the editor widget in the first editorstack (the one
                    # that can't be destroyed), then cloning this editor widget in
                    # all other editorstacks:
                    finfo, newname = self.load_and_translate(filename, pythonfile, editor, action)
                    finfo.path = editor.main.get_spyder_pythonpath()
                    editor._clone_file_everywhere(finfo)
                    current_editor = current_es.set_current_filename(newname)
                    
                    current_es.analyze_script()
                if goto is not None: # 'word' is assumed to be None as well
                    current_editor.go_to_line(goto[index], word=word)
                    position = current_editor.get_position('cursor')
                    editor.cursor_moved(filename0, position0, filename, position)
                if (current_editor is not None):
                    current_editor.clearFocus()
                    current_editor.setFocus()
                    current_editor.window().raise_()
                if processevents:
                    QApplication.processEvents()

    def load_and_translate(self, inputfile, pythonfile, editor, action, set_current=True):
        """
        If the input is COMBINE archive, read filename as combine archive, 
        unzip, translate, reconstitute in Python or PhrasedML, and create an 
        editor instance and return it
        If the input is SED-ML file, read filename as SED-ML file, translate 
        it to Python, and create an editor instance and return it
        *Warning* This is loading file, creating editor but not executing
        the source code analysis -- the analysis must be done by the editor
        plugin (in case multiple editorstack instances are handled)
        """
        inputfile = str(inputfile)
        text, enc = encoding.read(inputfile)
        if action == 'c2p':
            fformat = '.py'
            text = Translatecombine2P(inputfile)
            zipextloctemp, sbmlloclisttemp, sedmlloclisttemp = manifestsearch(inputfile)
        elif action == 'c2pwp':
            fformat = '_phrasedml.py'
            text = Translatecombine2WP(inputfile)
            zipextloctemp, sbmlloclisttemp, sedmlloclisttemp = manifestsearch(inputfile)
        elif action == 's2p':
            fname = os.path.basename(inputfile)
            temp =  '"End of code generated by Import SED-ML plugin ' + time.strftime("%m/%d/%Y") + '"\n"Extracted from ' + fname + '"\n\n'
            text = te.sedmlToPython(inputfile) + temp
        else:
            fname = os.path.basename(inputfile)
            temp =  '"End of code generated by Import SED-ML with PhrasedML plugin ' + time.strftime('%m/%d/%Y') + '"\n"Extracted from ' + fname + '"'
            text = "import tellurium as te\n\nphrasedmlStr = '''" + pl.convertFile(inputfile) + "'''\n\nte.executeSEDML(te.sedml.tephrasedml.phrasedml.convertString(phrasedmlStr))\n\n" + temp
        if action == 'c2p' or action == 'c2pwp':
            for i in range(len(text)):
                widgeteditor = editor.editorstacks[0]
                widgeteditor.starting_long_process.emit(_("Loading %s...") % inputfile)
                sedmlfname = os.path.basename(sedmlloclisttemp[i])
                finfo = widgeteditor.create_new_editor(os.path.splitext(sedmlfname)[0] + fformat, enc, text[i], set_current, new=True)
                index = widgeteditor.data.index(finfo)
                widgeteditor._refresh_outlineexplorer(index, update=True)
                widgeteditor.ending_long_process.emit("")
                if widgeteditor.isVisible() and widgeteditor.checkeolchars_enabled \
                 and sourcecode.has_mixed_eol_chars(text[i]):
                    if action == 'c2p':
                        name = os.path.basename(os.path.splitext(sedmlfname)[0] + fformat)
                    else:
                        name = os.path.basename(pythonfile[:-3] + fformat)
                    QMessageBox.warning(self, widgeteditor.title,
                                        _("<b>%s</b> contains mixed end-of-line "
                                          "characters.<br>Spyder will fix this "
                                          "automatically.") % name,
                                        QMessageBox.Ok)
                    widgeteditor.set_os_eol_chars(index)
                widgeteditor.is_analysis_done = False
                finfo.editor.set_cursor_position('eof')
                finfo.editor.insert_text(os.linesep)
        else:
            widgeteditor = editor.editorstacks[0]
            widgeteditor.starting_long_process.emit(_("Loading %s...") % inputfile)
            finfo = widgeteditor.create_new_editor(pythonfile, enc, text, set_current, new=True)
            index = widgeteditor.data.index(finfo)
            widgeteditor._refresh_outlineexplorer(index, update=True)
            widgeteditor.ending_long_process.emit("")
            if widgeteditor.isVisible() and widgeteditor.checkeolchars_enabled \
              and sourcecode.has_mixed_eol_chars(text):
                name = os.path.basename(pythonfile)
                QMessageBox.warning(self, widgeteditor.title,
                                    _("<b>%s</b> contains mixed end-of-line "
                                      "characters.<br>Spyder will fix this "
                                      "automatically.") % name,
                                      QMessageBox.Ok)
                widgeteditor.set_os_eol_chars(index)
            widgeteditor.is_analysis_done = False
            finfo.editor.set_cursor_position('eof')
            finfo.editor.insert_text(os.linesep)
        return finfo, inputfile

#Extracts combine archive to a temporary directory
def zipext(combine):
    tarzip = zipfile.ZipFile(combine)
    extloc = tempfile.mkdtemp()
    tarzip.extractall(extloc)
    tarzip.close()
    return extloc
    
#Searches the manifest to acquire correct sbml and sedml file location
def manifestsearch(combine):
    __manifest = True
    sbmlloclist = []
    sedmlloclist = []
    zipextloc = zipext(combine)
    manifestloc = os.path.join(zipextloc, 'manifest.xml')
    try:
        manifest = ElementTree.parse(manifestloc)
    except IOError:
        __manifest = False
    if __manifest == True:
        root = manifest.getroot()
        for child in root:
            attribute = child.attrib
            formtype = attribute.get('format')
            loc = attribute.get('location')
            if formtype == "http://identifiers.org/combine.specifications/sbml":
                sbmlloc = loc
                sbmlloclist.append(sbmlloc)
            elif formtype == "http://identifiers.org/combine.specifications/sed-ml":
                sedmlloc = loc
                sedmlloclist.append(sedmlloc)
        return (zipextloc, sbmlloclist, sedmlloclist)
    else:
        print ("Manifest file not found. teImport plugin will search for the model file...")


#Garbage collection
def delseq(floc):
    try:
        os.remove(floc)
    except OSError as E1:
        try:
            shutil.rmtree(floc)
        except OSError as E2:
            if E1.errno != errno.ENOENT or E2.errno != errno.ENOENT:
                raise

#Customized from Ipythonify
def Translatecombine2P(combine):
    
    #Creates a string with both SBML and SEDML included
    def translate(combine, filename):
        sbmlstrlist = []
        sedmlstrlist = []
        outputstrlist = []
        rePath = r"loadSBMLModel\((.*)\)"
        reFig = r"savefig\((.*)\)"
        outputstr = '"End of code generated by Import Combine plugin ' + time.strftime("%m/%d/%Y") + '"\n"Extracted from ' + filename + '"\n'
        zipextloc, sbmlloclist, sedmlloclist = manifestsearch(combine)
            
        for i in range(len(sbmlloclist)):
            sbml = te.readFromFile(os.path.join(zipextloc,sbmlloclist[i]))
            try:
                transtext = te.sbmlToAntimony(sbml)
            except Exception as e:
                transtext = """*********************WARNING*********************
Failed to translate the SBML model to Antimony string.
Please check that the SBML file is valid.
*********************WARNING*********************"""
                transtext = transtext + "\n\n" + str(e)
            sbmlstrlist.append(transtext)
        for j in range(len(sedmlloclist)):
            sedmlstr = te.sedmlToPython(os.path.join(zipextloc,sedmlloclist[j]))
            lines = sedmlstr.splitlines()
            for i,s in enumerate(lines):
                reSearchPath = re.split(rePath, s)
                if len(reSearchPath) > 1:
                    s = s.replace("loadSBMLModel", "loada")
                    s = s.replace(reSearchPath[1],"AntimonyModel")
                    lines[i] = s
                    lines.insert(i - 1, "AntimonyModel = '''\n" + sbmlstrlist[0] + "'''\n")
            for i,s in enumerate(lines):
                reSearchFig = re.split(reFig, s)
                if len(reSearchFig) > 1:
                    del lines[i]
            
            sedmlstr = '\n'.join(lines)
            
            sedmlstrlist.append(sedmlstr)

        for k in range(len(sedmlstrlist)):
            outputstrlist.append(sedmlstrlist[k] + '\n\n' + outputstr)
        
        delseq(zipextloc)
        return outputstrlist
                
    fname = os.path.basename(combine)
    return translate(combine, fname)

def Translatecombine2WP(combine):

    def getbasename(path):
        e = re.compile(r'.*[/\\]([^/\\]*\.[^/\\]*)')
        m = e.match(path)
        if m is None:
            raise RuntimeError('Path not recognized: {}'.format(path))
        return m.groups()[0]
						
    #Creates a string with both SBML and SEDML included
    def translate(combine, filename):
        sbmlstrlist = []
        sedmlstrlist = []
        outputstrlist = []
        outputstr = '"End of code generated by Import Combine as PhrasedML plugin ' + time.strftime("%m/%d/%Y") + '"\n"Extracted from ' + filename + '"\n'
        zipextloc, sbmlloclist, sedmlloclist = manifestsearch(combine)
        for i in range(len(sbmlloclist)):
            sbml = te.readFromFile(os.path.join(zipextloc,sbmlloclist[i]))
            try:
                transtext = te.sbmlToAntimony(sbml)
            except Exception as e:
                transtext = """*********************WARNING*********************
Failed to translate the SBML model to Antimony string.
Please check that the SBML file is valid.
*********************WARNING*********************"""
                transtext = transtext + "\n\n" + str(e)
            sbmlstrlist.append(transtext)
        for j in range(len(sedmlloclist)):
            sedmlstr = pl.convertFile(os.path.join(zipextloc,sedmlloclist[j]))
            sedmlstr = sedmlstr.replace('"compartment"', '"compartment_"')
            sedmlstr = sedmlstr.replace("'compartment'", "'compartment_'")
            sedmlstrlist.append(sedmlstr)
        
        for k in range(len(sedmlstrlist)):
            outputstrlist.append("AntimonyModel = '''\n" + sbmlstrlist[0] + "'''\n\nPhrasedMLstr = '''\n" + sedmlstrlist[k] + 
            "'''\n\nimport tellurium as te\n\nexp = te.experiment([AntimonyModel], [PhrasedMLstr])\nexp.execute(PhrasedMLstr)\n\n" + outputstr)
        
        delseq(zipextloc)
        return outputstrlist
                
    fname = os.path.basename(combine)
    return translate(combine, fname)
