from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class NewsArticle:
    title: str
    url: str
    source: str
    published: datetime
    summary: str = ""
    category: str = ""

    @property
    def display_text(self) -> str:
        source_label = f"[{self.source}]" if self.source else ""
        return f"{source_label} {self.title}\n{self.url}"


@dataclass(frozen=True)
class WeatherReport:
    city: str
    temperature: float
    feels_like: float
    humidity: int
    description: str
    wind_speed: float
    icon: str = ""

    @property
    def display_text(self) -> str:
        return (
            f"{self.city}: {self.temperature:.0f}°C "
            f"(cảm giác {self.feels_like:.0f}°C)\n"
            f"{self.description} | "
            f"Độ ẩm: {self.humidity}% | "
            f"Gió: {self.wind_speed:.1f} m/s"
        )


@dataclass(frozen=True)
class ScoreBreakdown:
    recency: float = 0.0
    source_trust: float = 0.0
    trending: float = 0.0
    keyword_boost: float = 0.0


@dataclass(frozen=True)
class ScoredArticle:
    article: NewsArticle
    score: float = 0.0
    category: str = "Khác"
    category_emoji: str = "📋"
    trending_sources: list[str] = field(default_factory=list)
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)

    @property
    def is_trending(self) -> bool:
        return len(self.trending_sources) >= 2


@dataclass(frozen=True)
class DailyForecast:
    day_label: str
    temp_min: float
    temp_max: float
    description: str = ""


@dataclass(frozen=True)
class DisasterAlert:
    title: str
    description: str
    severity: AlertSeverity
    source: str
    url: str
    published: datetime
    keywords_matched: list[str] = field(default_factory=list)

    @property
    def severity_emoji(self) -> str:
        return {
            AlertSeverity.LOW: "🟡",
            AlertSeverity.MEDIUM: "🟠",
            AlertSeverity.HIGH: "🔴",
            AlertSeverity.CRITICAL: "🚨",
        }.get(self.severity, "⚪")

    @property
    def display_text(self) -> str:
        return (
            f"{self.severity_emoji} [{self.severity.value.upper()}] {self.title}\n"
            f"{self.description}\n"
            f"Nguồn: {self.source} | {self.url}"
        )
