"""
Configuration for Compliance Document Review example.

This example demonstrates all 17 OpenIntent RFCs working together.
"""

import os

# OpenIntent server configuration
OPENINTENT_URL = os.getenv("OPENINTENT_URL", "http://localhost:8000")
OPENINTENT_API_KEY = os.getenv("OPENINTENT_API_KEY", "dev-agent-key")

# Dashboard configuration
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

# Agent definitions with their RFC showcase features
AGENTS = {
    "ocr": {
        "id": "ocr-agent",
        "description": "Document extraction with retry policy",
        "rfc_showcase": "RFC-0010 (Retry Policies)",
    },
    "analyzer": {
        "id": "analyzer-agent",
        "description": "Clause analysis with exclusive leasing",
        "rfc_showcase": "RFC-0003 (Leasing)",
    },
    "risk": {
        "id": "risk-agent",
        "description": "Risk assessment with cost tracking",
        "rfc_showcase": "RFC-0009 (Cost Tracking)",
    },
    "report": {
        "id": "report-agent",
        "description": "Report generation with attachments",
        "rfc_showcase": "RFC-0005 (Attachments)",
    },
}

# Simulated processing times (seconds)
SIMULATED_OCR_TIME = 2
SIMULATED_ANALYSIS_TIME = 3
SIMULATED_RISK_TIME = 2
SIMULATED_REPORT_TIME = 2
