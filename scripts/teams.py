"""Send alerts to Microsoft Teams channels.

Two channels, configured with environment variables (see .env.example):
  TEAMS_DATA_WEBHOOK_URL  -> data quality alerts (ingestion DAG, Grafana)
  TEAMS_ML_WEBHOOK_URL    -> ML alerts (training DAG, Grafana)

The payload is an Adaptive Card wrapped in a "message" envelope, which is accepted
both by classic Teams incoming webhooks and by Power Automate "Workflows" webhooks.
If no URL is configured the alert is only logged, so the pipeline never fails because
of a missing webhook.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)
CHANNELS = {"data": "TEAMS_DATA_WEBHOOK_URL", "ml": "TEAMS_ML_WEBHOOK_URL"}


def build_card(title: str, facts: dict, link: str = "", link_title: str = "Open report",
               severity: str = "attention") -> dict:
    body = [
        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium",
         "color": severity, "wrap": True},
        {"type": "FactSet", "facts": [{"title": str(k), "value": str(v)} for k, v in facts.items()]},
    ]
    card = {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard", "version": "1.4", "body": body}
    if link:
        card["actions"] = [{"type": "Action.OpenUrl", "title": link_title, "url": link}]
    return {"type": "message", "attachments": [
        {"contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None, "content": card}]}


def send_alert(channel: str, title: str, facts: dict, link: str = "", link_title: str = "Open report",
               severity: str = "attention") -> bool:
    """Post an alert. Returns True when Teams accepted it, False when only logged."""
    url = os.getenv(CHANNELS[channel], "").strip()
    summary = f"[{channel.upper()} ALERT] {title} | " + ", ".join(f"{k}={v}" for k, v in facts.items())
    if link:
        summary += f" | {link}"
    print(summary)
    if not url or "example.invalid" in url:
        print(f"{CHANNELS[channel]} is not configured: alert logged only.")
        return False
    try:
        response = requests.post(url, json=build_card(title, facts, link, link_title, severity), timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        # An alerting outage must not break the data pipeline.
        log.warning("Teams alert could not be delivered: %s", exc)
        print(f"Teams alert could not be delivered: {exc}")
        return False
