@echo off
setlocal

if not exist build mkdir build

rc /nologo /fo build\AutoAdderSetup.res AutoAdderSetup.rc

cl /nologo /std:c++17 /EHsc /DUNICODE /D_UNICODE /utf-8 ^
  AutoAdderSetup.cpp ^
  build\AutoAdderSetup.res ^
  /link /SUBSYSTEM:WINDOWS shell32.lib ole32.lib user32.lib ^
  /OUT:build\AutoAdderSetup.exe

endlocal
