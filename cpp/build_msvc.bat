@echo off
setlocal

if not exist build mkdir build

rc /nologo /fo build\AutoAdderWin.res AutoAdderWin.rc

cl /nologo /std:c++17 /EHsc /DUNICODE /D_UNICODE /utf-8 ^
  AutoAdderWin.cpp ^
  build\AutoAdderWin.res ^
  /link /SUBSYSTEM:WINDOWS comdlg32.lib comctl32.lib shell32.lib user32.lib gdi32.lib ^
  /OUT:build\AutoAdder.exe

endlocal
