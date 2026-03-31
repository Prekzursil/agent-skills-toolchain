# WinDbg Preview Notes

## Local launch

- Command: `windbg-preview`
- Shim target: `%USERPROFILE%\.local\bin\windbg-preview.cmd`

## Primary local artifact

- `C:\Users\Prekzursil\Downloads\swfoc_memory\StarWarsG.DMP`

## Suggested first command

Use the preview shim to open the SWFOC dump directly:

`windbg-preview -z "C:\Users\Prekzursil\Downloads\swfoc_memory\StarWarsG.DMP"`

Capture the exception, active thread, and loaded module list before moving to a disassembler.
