"""(18/11) Tope de memoria al abrir fotos (imagen._abrir): bytes, megapíxeles y reducción al decodificar. Sin red."""
import io

import pytest
from PIL import Image

import imagen


def _jpg(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 60)).save(b, format="JPEG", quality=60)
    return b.getvalue()


def test_abre_reducida_y_compone_igual():
    img = imagen._abrir(_jpg(3000, 2000))
    assert max(img.size) <= imagen.MAX_LADO and abs(img.size[0] / img.size[1] - 1.5) < 0.01
    assert imagen._abrir(_jpg(800, 600)).size == (800, 600)            # chica: no se toca
    jpg = imagen.componer_imagen(_jpg(3000, 2000), "La gratitud", logo=None)
    assert Image.open(io.BytesIO(jpg)).size == (1080, 1080)


def test_rechaza_demasiado_grande(monkeypatch):
    monkeypatch.setattr(imagen, "MAX_PIXELES", 1_000_000)
    with pytest.raises(ValueError, match="megapíxeles"):
        imagen._abrir(_jpg(1200, 1000))
    monkeypatch.setattr(imagen, "MAX_BYTES", 1000)
    with pytest.raises(ValueError, match="MB"):
        imagen._abrir(_jpg(800, 600))


def test_url_con_tope_de_bytes(monkeypatch):
    import urllib.request

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    datos = _jpg(400, 300)
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _R(datos))
    assert imagen._abrir("https://x/f.jpg").size == (400, 300)
    monkeypatch.setattr(imagen, "MAX_BYTES", len(datos) - 1)
    with pytest.raises(ValueError, match="MB"):
        imagen._abrir("https://x/f.jpg")
