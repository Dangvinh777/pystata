'''
This module is used to configure the system and display current system information 
and settings.
'''
from __future__ import absolute_import, print_function
from ctypes import cdll, c_char_p, c_int, POINTER
import os
from os.path import dirname
import sys
import platform
from pystata.stexception import IPythonError, IPyKernelError
import codecs
import atexit

def _find_lib(st_home, edition, os_system):
    lib_name = ""	
    if os_system == 'Windows':
        lib_name += (edition + '-64')
        lib_name += '.dll'
        lib_path = os.path.join(st_home, lib_name)
        if os.path.isfile(lib_path):
            return lib_path
    elif os_system == 'Darwin':
        lib_name += 'libstata'
        lib_name += ('-' + edition)
        lib_name += '.dylib'

        if edition == 'be':
            lib_name = os.path.join("StataBE.app/Contents/MacOS", lib_name)
        elif edition == "se":
            lib_name = os.path.join("StataSE.app/Contents/MacOS", lib_name)
        else:
            lib_name = os.path.join("StataMP.app/Contents/MacOS", lib_name)

        lib_path = os.path.join(st_home, lib_name)
        if os.path.isfile(lib_path):
            return lib_path
    else:
        lib_name += 'libstata'

        if edition != 'be':
            lib_name += ('-' + edition)

        lib_name += '.so'
        lib_path = os.path.join(st_home, lib_name)
        if os.path.isfile(lib_path):
            return lib_path

        lib_path = os.path.join('../distn/linux64', lib_name)
        lib_path = os.path.join(st_home, lib_path)
        if os.path.isfile(lib_path):
            return lib_path

        lib_path = os.path.join('../distn/linux.64p', lib_name)
        lib_path = os.path.join(st_home, lib_path)
        if os.path.isfile(lib_path):
            return lib_path

        lib_path = os.path.join('../distn/linux.64', lib_name)
        lib_path = os.path.join(st_home, lib_path)
        if os.path.isfile(lib_path):
            return lib_path

    return None


def _get_lib_path(st_home, edition):
    if st_home is None:
        raise ValueError('Stata home directory is None')
    else:
        if not os.path.isdir(st_home):
            raise ValueError('Stata home directory is invalid')

    os_system = platform.system()
    if edition not in ['be','se','mp']:
        raise ValueError('Stata edition must be one of be, se, or mp')

    lib_path = _find_lib(st_home, edition, os_system)
    if lib_path is not None:
        return lib_path

    raise FileNotFoundError('The system cannot find the shared library within the specified path: %s', st_home)


def _RaiseSystemException(msg):
    raise SystemError(msg)


stlib = None
stversion = ''
stedition = ''
stinitialized = False
sfiinitialized = False
stlibpath = None
stipython = 0
stoutputf = None

stconfig = {
    "grwidth": ['default', 'in'],
    "grheight": ['default', 'in'],
    "grformat": 'svg',
    "grshow": True,
    "streamout": 'on'
}

pyversion = sys.version_info[0:3]


def _check_duplicate_kmp(edition):
    os_system = platform.system()

    if edition is None or edition=='mp':
        if os_system == 'Darwin':
            os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'


def _get_stata_edition(edition):
    if edition is None:
        return 'MP'
    elif edition=='mp': 
        return 'MP'
    elif edition=='se':
        return 'SE'
    else:
        return 'BE'


def get_encode_str(s):
    return s.encode('utf-8')


def _print_greeting_message(msg):
    global pyversion

    try:
        print(msg, end='')
    except UnicodeEncodeError:
        if pyversion[0] < 3:
            print(s.encode('utf-8'), end='')
        else:
            print(s.encode('utf-8').decode(sys.stdout.encoding), end='')


def backslashreplace_py2(err):
    s = err.object
    start = err.start
    end = err.end

    def backslashreplace_repr(c):
        if isinstance(c,int):
            return c
        else:
            return ord(c)

    return u''.join('\\x{:x}'.format(backslashreplace_repr(c)) for c in s[start:end]),end


def get_decode_str(s):
    try:
        return s.decode('utf-8', 'backslashreplace')
    except:
        codecs.register_error('backslashreplace_py2', backslashreplace_py2)
        return s.decode('utf-8', 'backslashreplace_py2')


def _get_st_home():
    pypath = os.path.normpath(os.path.abspath(__file__))
    d_utilities = dirname(dirname(pypath))

    if os.path.basename(d_utilities).lower()=="utilities":
        return dirname(d_utilities)
    else:
        _RaiseSystemException("failed to load Stata's shared library")


def _get_executable_path():
    sys_exec_path = sys.executable
    if os.path.isfile(sys_exec_path):
        return sys_exec_path

    os_system = platform.system()
    if os_system!="Windows":
        sys_exec_path_non_windows = os.path.join(os.__file__.split('lib/')[0], 'bin', 'python')
        if os.path.isfile(sys_exec_path_non_windows):
            return sys_exec_path_non_windows

    return sys_exec_path


def _init_stata():
    stlib.StataSO_Main.restype = c_int
    stlib.StataSO_Main.argtypes = (c_int, POINTER(c_char_p))

    libpath = ['-pyexec', _get_executable_path()]
    sarr = (c_char_p * len(libpath))()
    sarr[:] = [get_encode_str(s) for s in libpath]
    
    rc = stlib.StataSO_Main(2, sarr)

    return(rc)


def init(edition):
    """
    Initialize Stata's environment within Python.

    Parameters
    ----------
    edition : str
        The Stata edition to be used. It can be one of **mp**, **se**, or **be**.
    """
    global stinitialized
    global sfiinitialized
    global stlibpath
    global stlib
    global stedition
    global stipython
    if stinitialized is False:
        st_home = _get_st_home()
        os.environ['SYSDIR_STATA'] = st_home
        lib_path = os.path.normpath(_get_lib_path(st_home, edition))
        stlibpath = lib_path
        stedition = _get_stata_edition(edition)

        try:
            stlib = cdll.LoadLibrary(lib_path)
        except:
            _RaiseSystemException("failed to load Stata's shared library")

        if stlib is None:
            _RaiseSystemException("failed to load Stata's shared library")		

        sfiinitialized = True
        rc = _init_stata()
        msg = get_output()
        if rc < 0:
            if rc==-7100:
                sfiinitialized = False
            else:
                _RaiseSystemException("failed to initialize Stata"+'\n'+msg)
        else:
            _print_greeting_message(msg)
	
        stinitialized = True
        _load_system_config()

        stipython = 0
        try:
            import pystata.ipython.stpymagic
            if stipython == 0:
                stipython = 5	    
        except IPythonError:
            pass 
        except IPyKernelError:
            pass
        except:
            stipython = 5

        if sys.version_info[0] < 3:
            reload(sys)
            sys.setdefaultencoding('utf-8')

        _check_duplicate_kmp(edition)


def check_initialized():
    if stinitialized is False:
        _RaiseSystemException('''
    Note: Stata environment has not been initialized yet. 
    To proceed, you must call init() function in the config module as follows:

        from pystata import config
        config.init()''')


@atexit.register
def shutdown():
    global stlib
    global stinitialized

    if stinitialized:
        try:
            stlib.StataSO_Shutdown.restype = None
            stlib.StataSO_Shutdown()
        except:
            raise


def is_stata_initialized():
    """
    Check whether Stata has been initialized.

    Returns
    -------
    bool
        True if Stata has been successfully initialized.
    """	
    global stinitialized
    return stinitialized


def _get_python_version_str():
    global pyversion
    s = [str(i) for i in pyversion]
    return ".".join(s)


def _get_stata_version_str():
    global stversion
    global stedition
    if stversion=='':
        return stedition
    else:
        return 'Stata ' + stversion + ' (' + stedition + ')'


def get_graph_size_str(info):
    global stconfig
    if info=='gw':
        grwidth = stconfig['grwidth']
        if grwidth[0]=='default':
            return 'default'
        else:
            return str(grwidth[0])+grwidth[1]
    else:
        grheight = stconfig['grheight']
        if grheight[0]=='default':
            return 'default'
        else:
            return str(grheight[0])+grheight[1]


def status():
    """
    Display current system information and settings.
    """
    if stinitialized is False:
        print('Stata environment has not been initialized yet')
    else:
        print('    System information')
        print('      Python version         %s' % _get_python_version_str())
        print('      Stata version          %s' % _get_stata_version_str())
        print('      Stata library path     %s' % stlibpath)
        print('      Stata initialized      %s' % str(stinitialized))
        print('      sfi initialized        %s\n' % str(sfiinitialized))
        print('    Settings')
        print('      graphic display       ', stconfig['grshow'])  
        print('      graphic size          ', ' width = ', get_graph_size_str('gw'), ', height = ', get_graph_size_str('gh'), sep='')
        print('      graphic format        ', stconfig['grformat'])


def get_output():
    stlib.StataSO_GetOutputBuffer.restype = c_char_p
    foo = stlib.StataSO_GetOutputBuffer()

    mystr = get_decode_str(c_char_p(foo).value)
    return mystr


def get_stipython():
    global stipython
    return stipython


def set_graph_format(gformat, perm=False):
    """
    Set the file format used to export and display graphs. By default, 
    graphs generated by Stata are exported and displayed as SVG files.

    The supported formats are **svg**, **png**, and **pdf**. If **svg** or 
    **png** is specified, the graph is embedded. If **pdf** is specified, the 
    graph is exported to a PDF file in the current working directory with a 
    numeric name, such as 0.pdf, 1.pdf, 2.pdf, etc. This is useful when you 
    try to export a notebook to a PDF via LaTex and you want the graph to be 
    embedded.	

    Parameters
    ----------
    gformat : str
        The graph format. It can be **svg**, **png**, or **pdf**.

    perm  : bool, optional 
        When set to True, in addition to making the change right now, 
        the setting will be remembered and become the default 
        setting when you invoke Stata. Default is False.
    """
    global stconfig 

    if perm is not True and perm is not False:
        raise ValueError("perm must be a boolean value") 

    if gformat=='svg':	
        stconfig['grformat'] = 'svg'
    elif gformat=="png":
        stconfig['grformat'] = 'png'
    elif gformat=='pdf':
        stconfig['grformat'] = 'pdf'
    else:
        raise ValueError("invalid graph format")

    if perm:
        _save_system_config("grformat", stconfig['grformat'])


def _get_figure_size_info(ustr):
    finfo = []
    ustr = ustr.strip()
    if ustr.lower() == 'default':
        finfo.append('default')
        finfo.append('in')
    else:
        try:
            figsize = round(float(ustr))
            finfo.append(figsize)
            finfo.append('in')		
        except ValueError:
            if ustr[-2:] == 'px':
                figsize = ustr[:-2].strip()
                if figsize.lower()!='default':
                    try:
                        figsize =  int(round(float(figsize)))
                    except ValueError:
                        figsize = -1

                finfo.append(figsize)
                finfo.append('px')
            elif ustr[-2:] == 'in':
                figsize = ustr[:-2].strip()
                if figsize.lower()!='default':
                    try:
                        figsize =  float(figsize)
                    except ValueError:
                        figsize = -1

                finfo.append(figsize)
                finfo.append('in')
            elif ustr[-2:] == 'cm':
                figsize = ustr[:-2].strip()
                if figsize.lower()!='default':
                    try:
                        figsize =  float(figsize)
                    except ValueError:
                        figsize = -1

                    finfo.append(round(figsize, 3))
                else:
                    finfo.append(figsize)

                finfo.append('cm')         
            else:
                finfo.append(-1)
                finfo.append('in')

    return finfo


def _add_java_home_to_path():
    os_system = platform.system()
    if os_system=="Windows":
        import sfi
        javahome = sfi.Macro.getGlobal('c(java_home)')
        if javahome!='':
            javahome = os.path.join(javahome, 'bin')
            ospath = os.environ['PATH']

            if ospath not in ospath.split(';'):
                os.environ['PATH'] = os.environ.get('PATH') + ";" + javahome


def _load_system_config():
    if sfiinitialized:
        try:
            import sfi 
            grwidth_pref = sfi.Preference.getSavedPref('pystata', 'grwidth', '')
            grheight_pref = sfi.Preference.getSavedPref('pystata', 'grheight', '')

            if grwidth_pref!="" and grheight_pref!="":
                set_graph_size(width=grwidth_pref, height=grheight_pref)
            elif grwidth_pref!="":
                set_graph_size(width=grwidth_pref)
            elif grheight_pref!="":
                set_graph_size(height=grheight_pref)

            grformat_pref = sfi.Preference.getSavedPref('pystata', 'grformat', '')
            if grformat_pref!="":
                set_graph_format(gformat=grformat_pref)

            grshow_pref = sfi.Preference.getSavedPref('pystata', 'grshow', '')
            if grshow_pref!="":
                if grshow_pref=="1":
                    set_graph_show(show=True)
                else:
                    set_graph_show(show=False)

            streamout_pref = sfi.Preference.getSavedPref('pystata', 'streamout', '')
            if streamout_pref!="":
                if streamout_pref=="on":
                    set_streaming_output_mode(flag='on')
                else:
                    set_streaming_output_mode(flag='off')

            global stversion
            stversion = str(sfi.Scalar.getValue('c(stata_version)'))
	    
            _add_java_home_to_path()
        except:
            print('''
Warning: failed to load the system default configuration. The following 
settings will be applied:
            ''')
            status()


def _save_system_config(key, value):
    if sfiinitialized:
        try:
            import sfi 
            sfi.Preference.setSavedPref("pystata", key, value)		
        except:
            _RaiseSystemException("failed to store the specified setting") 


def set_graph_size(width=None, height=None, perm=False):
    """
    Set the graph size for images to be exported and displayed. By default, 
    the graphs generated by Stata are exported using a dimension of 5.5 inches 
    for the width by 4 inches for the height. Either the width or height must 
    be specified, and both may be specified. If only one is specified, the 
    other one is calculated from the aspect ratio.  

    The width or height can be specified as a floating-point number, a string 
    with a floating-point number and its unit, or **default**. The supported 
    units are inches (**in**), pixels (**px**), or centimeters (**cm**). If 
    no unit is specified, **in** is assumed. For example, **width = 3** sets 
    the width to 3 inches, which is the same as specifying **width = 3in**. 
    And **width = 300px** sets the width to 300 pixels.

    Parameters
    ----------
    width : float or str
        The graph width.

    height: float or str
        The graph height.

    perm  : bool, optional 
        When set to True, in addition to making the change right now, 
        the setting will be remembered and become the default 
        setting when you invoke Stata. Default is False.
    """
    if width is None and height is None:
        raise ValueError('one of width and height must be specified')

    if perm is not True and perm is not False:
        raise ValueError("perm must be a boolean value")

    if width:
        gwidth = _get_figure_size_info(str(width))
        if gwidth[0] != 'default' and gwidth[0] < 0:
            raise ValueError('graph width is invalid')
	
        gr_width = gwidth[0]
        gr_width_unit = gwidth[1]
    else:
        gr_width = 'default'
        gr_width_unit = 'in'

    if height:
        gheight = _get_figure_size_info(str(height))
        if gheight[0] != 'default' and gheight[0] < 0:
            raise ValueError('graph height is invalid')

        gr_height = gheight[0]
        gr_height_unit = gheight[1]
    else:
        gr_height = 'default'
        gr_height_unit = 'in'

    global stconfig
    grwidth = []
    grheight = []
    if width and height:
        grwidth.append(gr_width)
        grwidth.append(gr_width_unit)
        grheight.append(gr_height)
        grheight.append(gr_height_unit)
    elif width:
        grwidth.append(gr_width)
        grwidth.append(gr_width_unit)
        grheight.append('default')
        grheight.append(gr_width_unit)
    elif height:
        grwidth.append('default')
        grwidth.append(gr_height_unit)
        grheight.append(gr_height)
        grheight.append(gr_height_unit)
    else:
        grwidth.append(gr_width)
        grwidth.append(gr_width_unit)
        grheight.append(gr_height)
        grheight.append(gr_height_unit)

    stconfig['grwidth'] = grwidth
    stconfig['grheight'] = grheight

    if perm:
        _save_system_config("grwidth", str(grwidth[0])+grwidth[1])
        _save_system_config("grheight", str(grheight[0])+grheight[1])


def set_graph_show(show, perm=False):
    """
    Set whether the graphs generated by Stata are to be exported and 
    displayed. By default, the graphs are exported and displayed 
    in the output. If `show` is set to False, graphs will not be 
    exported and displayed. 

    Parameters
    ----------
    show : bool
        Export and display Stata-generated graphs in the output.

    perm  : bool, optional 
        When set to True, in addition to making the change right now, 
        the setting will be remembered and become the default 
        setting when you invoke Stata. Default is False.
    """
    global stconfig

    if perm is not True and perm is not False:
        raise ValueError("perm must be a boolean value") 

    if show is True:	
        stconfig['grshow'] = True
    elif show is False:
        stconfig['grshow'] = False
    else:
        raise TypeError("show must be a boolean value") 

    if perm:
        if show:
            _save_system_config("grshow", "1")
        else:
            _save_system_config("grshow", "0")


def set_streaming_output_mode(flag, perm=False):
    global stconfig

    if perm is not True and perm is not False:
        raise ValueError("perm must be a boolean value") 

    if flag == "on":
        stconfig['streamout'] = 'on'
    elif flag == "off":
        stconfig['streamout'] = 'off'
    else:
        raise ValueError("The value for output mode must be either on or off. Default is on.")

    if perm:
        _save_system_config("streamout", stconfig['streamout'])


def set_output_file(filename, replace=False):
    """
    Write Stata output to a text file. By default, Stata output is printed on
    the screen. The file extension may be **.txt** or **.log**. You must 
    supply a file extension if you want one because none is assumed.

    Parameters
    ----------
    filename : str
        Name of the text file.

    replace : bool, optional 
        Replace the output file if it exists. Default is False.
    """
    global pyversion
    global stoutputf
    
    if os.path.isfile(filename):
        if not replace:
            raise OSError(filename + ' already exists')

        os.remove(filename)

    if pyversion[0] < 3:
        f = open(filename, 'ab')
    else:
        f = open(filename, 'a', newline='\n', encoding='utf-8')

    stoutputf = f


def close_output_file():
    """
    Stop writing Stata output to a text file. This function should be used 
    after having used :meth:`~pystata.config.set_output_file`. If it returns 
    without an error, any Stata output that follows will instead be printed 
    on the screen.
    """
    global stoutputf
    if stoutputf is not None:
        stoutputf.close()

