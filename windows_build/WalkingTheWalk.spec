from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "windows_build" / "launcher.py")],
    pathex=[str(root / "src"), str(root / "windows_build")],
    hiddenimports=["OpenGL.platform.win32", "OpenGL.arrays.numpymodule"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True,
    name="WalkingTheWalk", console=True, upx=False,
    manifest=str(root / "windows_build" / "WalkingTheWalk.manifest"),
)
collection = COLLECT(
    exe, analysis.binaries, analysis.datas,
    name="WalkingTheWalk", upx=False,
)
