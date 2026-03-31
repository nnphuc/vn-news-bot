from __future__ import annotations

from vn_news_bot.config import get_display_categories, get_scoring_limits
from vn_news_bot.domain.models import (
    DailyForecast,
    DisasterAlert,
    NewsArticle,
    ScoredArticle,
    WeatherReport,
)
from vn_news_bot.services.weather import get_forecast_suggestion, get_weather_suggestion

_MD_SPECIAL = str.maketrans({"_": r"\_", "*": r"\*", "`": r"\`", "[": r"\["})
_HTML_SPECIAL = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})


def _escape_md(text: str) -> str:
    """Escape Telegram legacy Markdown V1 special characters."""
    return text.translate(_MD_SPECIAL)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return text.translate(_HTML_SPECIAL)


def format_news_message(articles: list[NewsArticle]) -> str:
    if not articles:
        return "Không có tin tức mới."

    lines = ["📰 *Tin tức mới nhất*\n"]
    for i, article in enumerate(articles, 1):
        lines.append(f"{i}. [{_escape_md(article.title)}]({article.url})")
        if article.source:
            lines.append(f"   _Nguồn: {_escape_md(article.source)}_\n")
    return "\n".join(lines)


def _format_article_line(item: ScoredArticle) -> str:
    title = _escape_md(item.article.title)
    if item.is_trending:
        sources = _escape_md(", ".join(item.trending_sources))
        return f"🔥 [{title}]({item.article.url}) · 📡 _{sources}_"
    source = _escape_md(item.article.source)
    return f"▸ [{title}]({item.article.url}) · _{source}_"


def format_scored_news_message(scored: list[ScoredArticle]) -> str:
    if not scored:
        return "Không có tin tức mới."

    display_cats = get_display_categories()
    per_cat = get_scoring_limits().get("per_category", 5)

    lines = ["📰 *Tin tức mới nhất*"]
    used_urls: set[str] = set()

    for cat in display_cats:
        match_set: set[str] = set(cat["match"])
        is_fallback = len(match_set) == 0

        if is_fallback:
            items = [s for s in scored if s.article.url not in used_urls]
        else:
            items = [
                s for s in scored if s.category in match_set and s.article.url not in used_urls
            ]

        items = items[:per_cat]
        if not items:
            continue

        lines.append("")
        lines.append(f"*{cat['label']}*")
        for item in items:
            lines.append(_format_article_line(item))
            used_urls.add(item.article.url)

    return "\n".join(lines)


def format_weather_message(reports: list[WeatherReport]) -> str:
    if not reports:
        return "Không có dữ liệu thời tiết."

    lines = ["🌤 *Dự báo thời tiết*\n"]
    for report in reports:
        suggestion = get_weather_suggestion(report)
        lines.append(f"📍 *{report.city}*")
        lines.append(f"🌡 {report.temperature:.0f}°C ({report.description})")
        lines.append(f"💧 {report.humidity}%  💨 {report.wind_speed:.1f}m/s")
        lines.append(f"👕 _{suggestion}_\n")
    return "\n".join(lines)


def _temp_emoji(temp: float) -> str:
    if temp >= 35:
        return "🔥"
    if temp >= 28:
        return "☀️"
    if temp >= 20:
        return "🌤"
    if temp >= 15:
        return "🌥"
    return "❄️"


def _desc_emoji(description: str) -> str:
    d = description.lower()
    if "mưa" in d or "rain" in d:
        return "🌧"
    if "giông" in d or "dông" in d:
        return "⛈"
    if "mây" in d or "cloud" in d:
        return "☁️"
    if "nắng" in d or "quang" in d:
        return "☀️"
    return "🌤"


def format_single_weather(
    report: WeatherReport,
    forecast: list[DailyForecast] | None = None,
) -> str:
    emoji = _temp_emoji(report.temperature)
    suggestion = get_weather_suggestion(report)

    lines = [
        f"{emoji} *Thời tiết {report.city}*",
        "",
        f"🌡 *{report.temperature:.0f}°C* ・ cảm giác {report.feels_like:.0f}°C",
        f"{_desc_emoji(report.description)} {report.description}",
        f"💧 Độ ẩm {report.humidity}% ・ 💨 Gió {report.wind_speed:.1f} m/s",
        "",
        f"👕 _{suggestion}_",
    ]

    if forecast:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("📅 *7 ngày tới*")
        lines.append("")
        for day in forecast:
            de = _desc_emoji(day.description)
            tip = get_forecast_suggestion(day)
            tip_str = f"  _{tip}_" if tip else ""
            lines.append(
                f"{de} *{day.day_label}*  "
                f"{day.temp_min:.0f}° → {day.temp_max:.0f}°  "
                f"{day.description}{tip_str}"
            )

    return "\n".join(lines)


def format_forecast_message(
    city: str,
    forecast: list[DailyForecast],
) -> str:
    lines = [f"📅 *Dự báo 7 ngày - {city}*", ""]
    for day in forecast:
        de = _desc_emoji(day.description)
        tip = get_forecast_suggestion(day)
        tip_str = f"  _{tip}_" if tip else ""
        lines.append(
            f"{de} *{day.day_label}*  "
            f"{day.temp_min:.0f}° → {day.temp_max:.0f}°  "
            f"{day.description}{tip_str}"
        )
    return "\n".join(lines)


def format_weather_alert(
    city: str,
    prev: WeatherReport,
    curr: WeatherReport,
) -> str:
    lines = [f"⚡ *Cảnh báo thời tiết - {city}*", ""]

    temp_diff = curr.temperature - prev.temperature
    if abs(temp_diff) >= 1:
        arrow = "📈" if temp_diff > 0 else "📉"
        lines.append(
            f"{arrow} Nhiệt độ: *{prev.temperature:.0f}°C → {curr.temperature:.0f}°C* "
            f"({temp_diff:+.0f}°)"
        )

    hum_diff = curr.humidity - prev.humidity
    if abs(hum_diff) >= 5:
        lines.append(f"💧 Độ ẩm: {prev.humidity}% → {curr.humidity}%")

    if curr.description != prev.description:
        lines.append(
            f"{_desc_emoji(prev.description)} {prev.description} → "
            f"{_desc_emoji(curr.description)} {curr.description}"
        )

    suggestion = get_weather_suggestion(curr)
    lines.append("")
    lines.append(f"🌡 Hiện tại: *{curr.temperature:.0f}°C* ・ {curr.description}")
    lines.append(f"👕 _{suggestion}_")
    return "\n".join(lines)


def format_disaster_message(alerts: list[DisasterAlert]) -> str:
    if not alerts:
        return "Không có cảnh báo thiên tai."

    lines = ["⚠️ <b>CẢNH BÁO THIÊN TAI</b>", ""]
    for alert in alerts:
        title = _escape_html(alert.title)
        desc = _escape_html(alert.description)
        source = _escape_html(alert.source)
        time_str = alert.published.strftime("%H:%M")
        lines.append(
            f'{alert.severity_emoji} <a href="{alert.url}"><b>{title}</b></a>\n'
            f"<blockquote>{desc}</blockquote>\n"
            f"<i>{source} · {time_str}</i>"
        )
        lines.append("")
    return "\n".join(lines)


def format_hot_news_digest(
    hot_articles: list[ScoredArticle],
    regular_articles: list[ScoredArticle],
) -> str:
    if not hot_articles and not regular_articles:
        return "Không có tin tức mới."

    lines: list[str] = []

    if hot_articles:
        lines.append("🔥 <b>TIN NÓNG</b>")
        lines.append("")
        for item in hot_articles:
            title = _escape_html(item.article.title)
            source = _escape_html(item.article.source)
            desc = _escape_html(item.article.summary)
            time_str = item.article.published.strftime("%H:%M")
            lines.append(
                f'📌 <a href="{item.article.url}"><b>{title}</b></a>\n'
                f"<blockquote>{desc}</blockquote>\n"
                f"<i>{source} · {time_str}</i>"
            )
            lines.append("")

    if regular_articles:
        lines.append("📰 <b>TIN TỨC</b>")
        lines.append("")
        for item in regular_articles:
            title = _escape_html(item.article.title)
            source = _escape_html(item.article.source)
            time_str = item.article.published.strftime("%H:%M")
            lines.append(
                f'▫️ <a href="{item.article.url}">{title}</a>\n'
                f"   <i>{source} · {time_str}</i>"
            )
            lines.append("")

    return "\n".join(lines)
