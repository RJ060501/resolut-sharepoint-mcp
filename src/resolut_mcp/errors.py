"""Only these deliberately non-sensitive messages may cross the MCP boundary."""

MESSAGES = {
    "unavailable": "Resource unavailable or access not permitted.",
    "authentication_required": "Sign in again through the connector.",
    "authorization_configuration": "Connector authorization configuration requires administrator review.",
    "policy_unavailable": "Approval policy is unavailable. No information was returned.",
    "upstream_unavailable": "Microsoft 365 is temporarily unavailable. Retry later.",
    "throttled": "Microsoft 365 is busy. Retry later.",
    "invalid_request": "Invalid request. Use identifiers returned by this connector.",
    "unsupported_format": "This authorized file format is not supported. Use TXT, DOCX, or a text-based PDF.",
    "file_too_large": "The authorized file exceeds the configured download limit.",
    "extraction_limit": "The authorized file exceeds the extraction size, page, or time limit.",
    "encrypted_file": "The authorized file is encrypted or password-protected and cannot be extracted.",
    "no_extractable_text": "No usable text was found. Image-only PDFs require OCR, which this connector does not perform.",
    "extraction_failed": "The authorized file could not be extracted safely.",
    "changed_during_read": "The file changed during retrieval. Retry to retrieve the current version.",
    "deadline": "The request reached its time limit. Narrow the search to one job or try again.",
    "busy": "The connector is busy. Retry later.",
    "internal_error": "The connector could not complete the request. Contact IT with the request reference.",
}


class ConnectorError(Exception):
    def __init__(self, code: str = "unavailable") -> None:
        self.code = code if code in MESSAGES else "internal_error"
        super().__init__(MESSAGES[self.code])
