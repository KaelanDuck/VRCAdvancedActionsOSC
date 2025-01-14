import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
# "packages": ["os"] is used as example only
packages = ["os", "json", "traceback", "openvr", "sys", "time", "ctypes", "argparse", "pythonosc", "yaml", "glm"]
exclude = ["tkinter", "asyncio", "concurrent", "html", "http", "lib2to3", "multiprocessing", "test", "unittest", "xmlrpc"]
file_include = ["config.yaml", "Run Debug Mode.bat", "openvr/", "bindings/", "example_configs/", "app.vrmanifest"]
bin_excludes = ["_bz2.pyd", "_decimal.pyd", "_hashlib.pyd", "_lzma.pyd", "_queue.pyd", "_ssl.pyd", "libcrypto-1_1.dll", "libssl-1_1.dll", "ucrtbase.dll", "VCRUNTIME140.dll"]

build_exe_options = {"packages": packages, "excludes": exclude, "include_files": file_include, "bin_excludes": bin_excludes}

setup(
    name="AdvancedActionsOSC",
    version="0.3.1",
    description="AdvancedActionsOSC",
    options={"build_exe": build_exe_options},
    executables=[Executable("AdvancedActionsOSC.py", targetName="AdvancedActionsOSC.exe", base=False, icon="icon.ico"), Executable("AdvancedActionsOSC.py", targetName="AdvancedActionsOSC_NoConsole.exe", base="Win32GUI", icon="icon.ico")],
)