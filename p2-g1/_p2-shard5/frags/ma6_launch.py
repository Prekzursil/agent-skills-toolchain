    def _spawn(self, argv_list: list[str]) -> tuple:
        try:
            return subprocess.run(argv_list, capture_output=True, text=True), False
        except OSError as exc:
            if os.name != "nt":
                raise
            head = Path(argv_list[0])
            if argv_list[0].lower().endswith((".exe", ".com", ".bat", ".cmd")):
                raise
            bash = shutil.which("bash")
            if bash is None:
                raise
            # 2026-10-24: Windows cannot exec shebang scripts (WinError 193).
            # Interpose the host POSIX shell so the contract stays testable
            # on Windows dev hosts; the interpreter dir is prepended to PATH
            # so fixture shells can exec python. Interposition is recorded on
            # Launched.shell_interposed, never hidden.
            env = os.environ.copy()
            env["PATH"] = (
                str(Path(sys.executable).resolve().parent)
                + os.pathsep
                + env.get("PATH", "")
            )
            proc = subprocess.run(
                [bash, *argv_list],
                capture_output=True,
                text=True,
                env=env,
            )
            return proc, True

    def launch(self, argv: Sequence[str], capture_uname: bool = False) -> Launched:
        argv_list = [str(a) for a in argv]
        self._preflight(argv_list)
        proc, interposed = self._spawn(argv_list)
        uname_inside = child_uname() if capture_uname else None
        return Launched(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            argv=argv_list,
            uname_inside=uname_inside,
            shell_interposed=interposed,
        )

    def launch_shell_script(self, script: Path | str) -> Launched:
        return self.launch([str(self.zsh()), str(script)])
