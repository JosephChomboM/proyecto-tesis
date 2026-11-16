from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def label(elements, name):
    return next(element for element in elements if element.label == name)


def test_render_without_access_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("RESTAURANTE_ACCESS_PASSWORD", raising=False)
    monkeypatch.setenv("RESTAURANTE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert not app.button
    assert not list(tmp_path.glob("*.sqlite3"))


def test_hosted_login_wrong_key_then_correct_and_workspace_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RESTAURANTE_ACCESS_PASSWORD", "test-only-access-key-123")
    monkeypatch.setenv("RESTAURANTE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    label(app.text_input, "Clave de acceso").set_value("wrong")
    label(app.button, "Entrar").click().run()
    assert app.error
    assert not list(tmp_path.glob("*.sqlite3"))
    label(app.text_input, "Clave de acceso").set_value("test-only-access-key-123")
    label(app.button, "Entrar").click().run()
    assert not app.exception
    label(app.button, "Comenzar mi restaurante").click().run()
    assert (tmp_path / "restaurant.sqlite3").exists()
    label(app.selectbox, "Espacio de trabajo").select("Demostración").run()
    assert not app.exception
    assert label(app.button, "Cerrar sesión")
    label(app.button, "Cerrar sesión").click().run()
    assert label(app.text_input, "Clave de acceso")


def test_repeated_invalid_access_is_temporarily_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RESTAURANTE_ACCESS_PASSWORD", "test-only-access-key-123")
    monkeypatch.setenv("RESTAURANTE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    for _ in range(5):
        label(app.text_input, "Clave de acceso").set_value("wrong")
        label(app.button, "Entrar").click().run()
    app.run()
    assert any("Espera un minuto" in item.value for item in app.warning)
    assert not app.button
    assert not list(tmp_path.glob("*.sqlite3"))


def test_public_demo_is_isolated_and_does_not_expose_own_restaurant(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RESTAURANTE_PUBLIC_DEMO", "true")
    monkeypatch.setenv("RESTAURANTE_DATA_DIR", str(tmp_path))
    first = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not first.exception
    assert all(button.label != "Comenzar mi restaurante" for button in first.button)
    label(first.button, "Explorar demostración").click().run()
    assert label(first.selectbox, "Espacio de trabajo").options == ["Demostración"]
    second = AppTest.from_file(str(APP), default_timeout=30).run()
    label(second.button, "Explorar demostración").click().run()
    assert first.session_state["demo_directory"].name != second.session_state["demo_directory"].name
    assert not list(tmp_path.glob("*.sqlite3"))
    first.session_state["mode"] = "Mi restaurante"
    first.run()
    assert first.session_state["mode"] == "Demostración"
