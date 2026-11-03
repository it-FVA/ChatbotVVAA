"""secretos.py: el cargador único de secretos locales."""
import os

import secretos


def test_carga_sin_pisar_el_entorno_y_devuelve_las_tablas(tmp_path, monkeypatch):
    f = tmp_path / "s.toml"
    f.write_text('A_NUEVA = "uno"\nYA_ESTA = "toml"\nN = 3\nB = true\n[usuarios]\nfranco = "x"\n', encoding="utf-8")
    monkeypatch.setenv("FVA_SECRETS", str(f))
    monkeypatch.setenv("YA_ESTA", "entorno")
    for k in ("A_NUEVA", "N", "B"):
        monkeypatch.delenv(k, raising=False)
    tablas = secretos.cargar_al_entorno()
    assert tablas == {"usuarios": {"franco": "x"}}
    assert (os.environ["A_NUEVA"], os.environ["YA_ESTA"], os.environ["N"], os.environ["B"]) == ("uno", "entorno", "3", "True")
    for k in ("A_NUEVA", "N", "B"):
        monkeypatch.delenv(k)


def test_avisa_si_no_encuentra_el_archivo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FVA_SECRETS", str(tmp_path / "no_existe.toml"))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert secretos.cargar_al_entorno() == {}
    assert "No encontré" in capsys.readouterr().err
    monkeypatch.setenv("SUPABASE_URL", "https://x")      # servidor con variables: no hace falta el archivo
    secretos.cargar_al_entorno()
    assert capsys.readouterr().err == ""


def test_guion_lo_desactiva(monkeypatch, capsys):
    monkeypatch.setenv("FVA_SECRETS", "-")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert secretos.cargar_al_entorno() == {}
    assert capsys.readouterr().err == ""
