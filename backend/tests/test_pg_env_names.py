"""The startup log names the injected PG* variables and never their values."""

from app.core.config import injected_pg_var_names


def test_only_names_of_pg_variables(monkeypatch):
    monkeypatch.setenv("PGHOST", "db.example.invalid")
    monkeypatch.setenv("PGPASSWORD", "s3cret-value")  # pragma: allowlist secret
    monkeypatch.setenv("PGUSER", "svc")
    monkeypatch.setenv("NOT_PG", "x")

    names = injected_pg_var_names()

    assert set(names) >= {"PGHOST", "PGPASSWORD", "PGUSER"}
    assert names == sorted(names)
    assert "NOT_PG" not in names
    assert not any("s3cret" in n or "example" in n for n in names)
