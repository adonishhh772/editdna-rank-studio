from app.services.ytdlp_command import (
    build_ytdlp_base_args,
    build_ytdlp_download_args,
    impersonation_available,
    resolve_impersonate_target,
    resolve_js_runtime,
    resolve_ytdlp_executable,
)


def test_resolve_ytdlp_executable_returns_command():
    executable = resolve_ytdlp_executable()
    assert len(executable) >= 1


def test_build_ytdlp_base_args_includes_remote_components():
    args = build_ytdlp_base_args()
    assert args[0] == resolve_ytdlp_executable()[0]
    assert "--remote-components" in args
    assert "ejs:github" in args
    if impersonation_available():
        assert "--impersonate" in args
        assert resolve_impersonate_target() in args


def test_impersonation_available_matches_curl_cffi_import():
    assert impersonation_available() == (resolve_impersonate_target() is not None)


def test_build_ytdlp_download_args_includes_output_template():
    args = build_ytdlp_download_args("/tmp/test.%(ext)s", "https://www.youtube.com/watch?v=abc123")
    assert "-o" in args
    assert "/tmp/test.%(ext)s" in args
    assert "https://www.youtube.com/watch?v=abc123" in args


def test_resolve_js_runtime_finds_node():
    runtime = resolve_js_runtime()
    if runtime is not None:
        runtime_name, runtime_path = runtime
        assert runtime_name in {"node", "deno"}
        assert runtime_path
