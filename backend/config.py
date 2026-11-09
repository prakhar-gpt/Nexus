"""Application, LLM provider, and authentication settings loaded from environment with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def _load_env_file() -> dict[str, str]:
    """Parse local .env key-value pairs as fallback if not present in os.environ."""
    env_vars: dict[str, str] = {}
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    env_vars[k] = v
        except Exception:
            pass
    return env_vars


_FILE_ENV = _load_env_file()


def _parse_database_url() -> dict[str, str]:
    """Parse DATABASE_URL to automatically infer PG_HOST, PG_DATABASE, etc."""
    db_url = os.environ.get("DATABASE_URL") or _FILE_ENV.get("DATABASE_URL")
    if not db_url:
        return {}
    try:
        from urllib.parse import urlparse
        p = urlparse(db_url)
        return {
            "database": p.path.lstrip("/") if p.path else "",
            "host": p.hostname or "",
            "port": str(p.port or 5432) if p.port else "5432",
            "user": p.username or "",
            "password": p.password or "",
        }
    except Exception:
        return {}


_DB_URL_PARTS = _parse_database_url()


def _get_str(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val is not None and val.strip():
        return val.strip().strip('"').strip("'")
    return _FILE_ENV.get(key, default)


def _get_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        val = _FILE_ENV.get(key)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None:
        val = _FILE_ENV.get(key)
    if val is None:
        return default
    try:
        return int(str(val).strip())
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    val = os.environ.get(key)
    if val is None:
        val = _FILE_ENV.get(key)
    if val is None:
        return default
    try:
        return float(str(val).strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # -----------------------------------------------------------------------
    # LLM Provider & Hosted Model Configuration
    # -----------------------------------------------------------------------
    MODEL_PROVIDER: str = field(default_factory=lambda: _get_str("MODEL_PROVIDER", "").lower())
    MODEL_NAME: str = field(default_factory=lambda: _get_str("MODEL_NAME", ""))
    MODEL_TEMPERATURE: float = field(default_factory=lambda: _get_float("MODEL_TEMPERATURE", 0.0))
    MODEL_MAX_TOKENS: int = field(default_factory=lambda: _get_int("MODEL_MAX_TOKENS", 800))

    # Provider API Keys
    GROQ_API_KEY: str = field(default_factory=lambda: _get_str("GROQ_API_KEY", ""))
    OPENROUTER_API_KEY: str = field(default_factory=lambda: _get_str("OPENROUTER_API_KEY", ""))
    DEEPSEEK_API_KEY: str = field(default_factory=lambda: _get_str("DEEPSEEK_API_KEY", ""))

    # Provider Base URLs & Default Model IDs
    GROQ_BASE_URL: str = field(default_factory=lambda: _get_str("GROQ_BASE_URL", "https://api.groq.com/openai/v1"))
    GROQ_DEFAULT_MODEL: str = field(default_factory=lambda: _get_str("GROQ_DEFAULT_MODEL", "openai/gpt-oss-120b"))

    OPENROUTER_BASE_URL: str = field(default_factory=lambda: _get_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    OPENROUTER_DEFAULT_MODEL: str = field(default_factory=lambda: _get_str("OPENROUTER_DEFAULT_MODEL", "openai/gpt-oss-120b"))

    DEEPSEEK_BASE_URL: str = field(default_factory=lambda: _get_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
    DEEPSEEK_DEFAULT_MODEL: str = field(default_factory=lambda: _get_str("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat"))

    # Database Passwords & Credentials
    NEXUS_WRITER_PASSWORD: str = field(default_factory=lambda: _get_str("NEXUS_WRITER_PASSWORD", "postgres"))
    NEXUS_READER_PASSWORD: str = field(default_factory=lambda: _get_str("NEXUS_READER_PASSWORD", ""))

    # Security & Hashing
    BCRYPT_ROUNDS: int = field(default_factory=lambda: _get_int("BCRYPT_ROUNDS", 12))

    # Sessions & Cookies
    SESSION_COOKIE_NAME: str = field(default_factory=lambda: _get_str("SESSION_COOKIE_NAME", "nexus_session"))
    SESSION_EXPIRY_DAYS: int = field(default_factory=lambda: _get_int("SESSION_EXPIRY_DAYS", 14))
    SESSION_IDLE_EXPIRY_DAYS: int = field(default_factory=lambda: _get_int("SESSION_IDLE_EXPIRY_DAYS", 7))
    SESSION_TOUCH_INTERVAL_SECONDS: int = field(default_factory=lambda: _get_int("SESSION_TOUCH_INTERVAL_SECONDS", 300))
    COOKIE_SECURE: bool = field(default_factory=lambda: _get_bool("COOKIE_SECURE", False))
    COOKIE_SAMESITE: str = field(default_factory=lambda: _get_str("COOKIE_SAMESITE", "lax").lower())

    # Registration & Lockout
    ALLOW_SIGNUP: bool = field(default_factory=lambda: _get_bool("ALLOW_SIGNUP", True))
    MAX_FAILED_LOGIN_ATTEMPTS: int = field(default_factory=lambda: _get_int("MAX_FAILED_LOGIN_ATTEMPTS", 5))
    LOCKOUT_MINUTES: int = field(default_factory=lambda: _get_int("LOCKOUT_MINUTES", 15))

    # Rate Limiting
    TRUSTED_PROXY_HEADERS: bool = field(default_factory=lambda: _get_bool("TRUSTED_PROXY_HEADERS", False))
    RATE_LIMIT_LOGIN_PER_MIN_IP: int = field(default_factory=lambda: _get_int("RATE_LIMIT_LOGIN_PER_MIN_IP", 5))
    RATE_LIMIT_LOGIN_PER_HOUR_IP: int = field(default_factory=lambda: _get_int("RATE_LIMIT_LOGIN_PER_HOUR_IP", 20))
    RATE_LIMIT_SIGNUP_PER_HOUR_IP: int = field(default_factory=lambda: _get_int("RATE_LIMIT_SIGNUP_PER_HOUR_IP", 5))
    RATE_LIMIT_CHANGE_PASSWORD_PER_HOUR_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_CHANGE_PASSWORD_PER_HOUR_USER", 5))
    RATE_LIMIT_CHAT_PER_MIN_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_CHAT_PER_MIN_USER", 30))
    RATE_LIMIT_UPLOAD_PER_HOUR_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_UPLOAD_PER_HOUR_USER", 10))
    RATE_LIMIT_API_PER_MIN_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_API_PER_MIN_USER", 120))
    MAX_CONCURRENT_SSE_PER_USER: int = field(default_factory=lambda: _get_int("MAX_CONCURRENT_SSE_PER_USER", 5))

    # CORS
    CORS_ORIGINS: list[str] = field(default_factory=lambda: list(dict.fromkeys([
        clean
        for raw in os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if raw.strip()
        for clean in (
            raw.strip().strip('"').strip("'").rstrip("/"),
            raw.strip().strip('"').strip("'").rstrip("/") + "/",
        )
        if clean
    ])))

    # -----------------------------------------------------------------------
    # Ingestion & Upload Constraints
    # -----------------------------------------------------------------------
    UPLOAD_MAX_BYTES: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_BYTES", 50 * 1024 * 1024))
    UPLOAD_MAX_ROWS: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_ROWS", 600_000))
    UPLOAD_MAX_COLUMNS: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_COLUMNS", 64))
    UPLOAD_HEADER_SCAN_ROWS: int = field(default_factory=lambda: _get_int("UPLOAD_HEADER_SCAN_ROWS", 20))
    UPLOAD_MAX_REGENERATE_RUNS: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_REGENERATE_RUNS", 3))
    UPLOAD_DIR: str = field(default_factory=lambda: os.environ.get("UPLOAD_DIR", "datasets/uploads"))
    UPLOAD_ALLOWED_EXTENSIONS: set[str] = field(default_factory=lambda: {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in os.environ.get("UPLOAD_ALLOWED_EXTENSIONS", ".csv,.xlsx").split(",")
        if ext.strip()
    })

    # =======================================================================
    # AGENT 1: NEXUS COPILOT (Analytical Chat Agent)
    # Location: backend/agent/nexus/
    # Role: Multi-turn analytics copilot answering retail/business questions
    #       over datasets using SQL, Python math sandbox, and retail knowledge.
    # =======================================================================

    # --- Nexus Copilot: Reasoning Loop & Context Bounds ---
    NEXUS_MAX_TOOL_STEPS: int = field(default_factory=lambda: _get_int(
        "NEXUS_MAX_TOOL_STEPS", _get_int("AGENT_MAX_TOOL_STEPS", 8)
    ))
    NEXUS_HISTORY_TURNS: int = field(default_factory=lambda: _get_int(
        "NEXUS_HISTORY_TURNS", _get_int("AGENT_HISTORY_TURNS", 8)
    ))
    NEXUS_MESSAGE_TAIL: int = field(default_factory=lambda: _get_int(
        "NEXUS_MESSAGE_TAIL", _get_int("AGENT_MESSAGE_TAIL", 20)
    ))

    # --- Nexus Copilot Tool 1: Guarded SQL Engine (run_sql) ---
    NEXUS_TOOL_SQL_TIMEOUT_MS: int = field(default_factory=lambda: _get_int(
        "NEXUS_TOOL_SQL_TIMEOUT_MS", _get_int("SQL_TIMEOUT_MS", 5000)
    ))
    NEXUS_TOOL_SQL_ROW_LIMIT: int = field(default_factory=lambda: _get_int(
        "NEXUS_TOOL_SQL_ROW_LIMIT", _get_int("SQL_ROW_LIMIT", 200)
    ))
    NEXUS_TOOL_SQL_PREVIEW_LIMIT: int = field(default_factory=lambda: _get_int(
        "NEXUS_TOOL_SQL_PREVIEW_LIMIT", _get_int("SQL_PREVIEW_LIMIT", 25)
    ))

    # --- Nexus Copilot Tool 2: Sandboxed Python Math Execution (run_python) ---
    NEXUS_TOOL_PYTHON_TIMEOUT_SECONDS: int = field(default_factory=lambda: _get_int(
        "NEXUS_TOOL_PYTHON_TIMEOUT_SECONDS", _get_int("PYTHON_SANDBOX_TIMEOUT_SECONDS", 10)
    ))
    NEXUS_TOOL_PYTHON_MEMORY_MB: int = field(default_factory=lambda: _get_int(
        "NEXUS_TOOL_PYTHON_MEMORY_MB", _get_int("PYTHON_SANDBOX_MEMORY_MB", 256)
    ))

    # --- Nexus Copilot Tool 3: Retail Knowledge Base (read_kb) ---
    NEXUS_TOOL_KB_MAX_CHARS: int = field(default_factory=lambda: _get_int(
        "NEXUS_TOOL_KB_MAX_CHARS", _get_int("KB_MAX_CHARS", 6000)
    ))
    NEXUS_TOOL_KB_DIR: str = field(default_factory=lambda: (
        os.environ.get("NEXUS_TOOL_KB_DIR") or os.environ.get("KB_DIR") or "backend/kb"
    ))

    # =======================================================================
    # AGENT 2: NEXUS ARCHITECT (Schema Profiler & Table Ingestion Agent)
    # Location: backend/agent/architect/
    # Role: Ingestion profiler inspecting uploaded CSV/XLSX spreadsheets,
    #       analyzing columns, determining grains/types, and proposing schemas.
    # =======================================================================

    # --- Nexus Architect: Reasoning Loop Bounds ---
    ARCHITECT_MAX_STEPS: int = field(default_factory=lambda: _get_int(
        "ARCHITECT_MAX_STEPS", 6
    ))

    # --- Nexus Architect Tools: Column Profiler & Value Sampler ---
    # Tools: profile_column, sample_values, check_date_distribution
    ARCHITECT_TOOL_SAMPLE_ROWS: int = field(default_factory=lambda: _get_int(
        "ARCHITECT_TOOL_SAMPLE_ROWS", _get_int("ARCHITECT_SAMPLE_ROWS", 30)
    ))
    ARCHITECT_TOOL_MAX_CELL_CHARS: int = field(default_factory=lambda: _get_int(
        "ARCHITECT_TOOL_MAX_CELL_CHARS", _get_int("ARCHITECT_MAX_CELL_CHARS", 80)
    ))
    ARCHITECT_TOOL_PREVIEW_ITEMS: int = field(default_factory=lambda: _get_int(
        "ARCHITECT_TOOL_PREVIEW_ITEMS", _get_int("ARCHITECT_PREVIEW_ITEMS", 5)
    ))

    # -----------------------------------------------------------------------
    # Database Runner & CLI Infrastructure
    # -----------------------------------------------------------------------
    PSQL_PATH: str = field(default_factory=lambda: os.environ.get("PSQL_PATH") or (import_shutil := __import__("shutil")).which("psql") or r"C:\Program Files\PostgreSQL\18\bin\psql.exe")
    PG_HOST: str = field(default_factory=lambda: _get_str("PGHOST", _DB_URL_PARTS.get("host", "localhost")))
    PG_PORT: str = field(default_factory=lambda: _get_str("PGPORT", _DB_URL_PARTS.get("port", "5432")))
    PG_READER_USER: str = field(default_factory=lambda: os.environ.get("PG_READER_USER", "nexus_reader"))
    PG_DATABASE: str = field(default_factory=lambda: _get_str("PGDATABASE", _DB_URL_PARTS.get("database", "nexus_db")))

    # -----------------------------------------------------------------------
    # Backward-Compatibility Aliases
    # -----------------------------------------------------------------------
    @property
    def AGENT_MAX_TOOL_STEPS(self) -> int:
        return self.NEXUS_MAX_TOOL_STEPS

    @property
    def AGENT_HISTORY_TURNS(self) -> int:
        return self.NEXUS_HISTORY_TURNS

    @property
    def AGENT_MESSAGE_TAIL(self) -> int:
        return self.NEXUS_MESSAGE_TAIL

    @property
    def SQL_TIMEOUT_MS(self) -> int:
        return self.NEXUS_TOOL_SQL_TIMEOUT_MS

    @property
    def SQL_ROW_LIMIT(self) -> int:
        return self.NEXUS_TOOL_SQL_ROW_LIMIT

    @property
    def SQL_PREVIEW_LIMIT(self) -> int:
        return self.NEXUS_TOOL_SQL_PREVIEW_LIMIT

    @property
    def PYTHON_SANDBOX_TIMEOUT_SECONDS(self) -> int:
        return self.NEXUS_TOOL_PYTHON_TIMEOUT_SECONDS

    @property
    def PYTHON_SANDBOX_MEMORY_MB(self) -> int:
        return self.NEXUS_TOOL_PYTHON_MEMORY_MB

    @property
    def KB_MAX_CHARS(self) -> int:
        return self.NEXUS_TOOL_KB_MAX_CHARS

    @property
    def KB_DIR(self) -> str:
        return self.NEXUS_TOOL_KB_DIR

    @property
    def ARCHITECT_SAMPLE_ROWS(self) -> int:
        return self.ARCHITECT_TOOL_SAMPLE_ROWS

    @property
    def ARCHITECT_MAX_CELL_CHARS(self) -> int:
        return self.ARCHITECT_TOOL_MAX_CELL_CHARS

    @property
    def ARCHITECT_PREVIEW_ITEMS(self) -> int:
        return self.ARCHITECT_TOOL_PREVIEW_ITEMS


settings = Settings()
