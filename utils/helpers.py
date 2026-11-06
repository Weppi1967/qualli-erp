import csv
import io
import re
from datetime import date, datetime

from flask import Response, current_app, jsonify, request


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


def error_response(message, status=400, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def get_json():
    data = request.get_json(silent=True)
    if data is None:
        if request.data:
            raise ApiError("Ungültiges JSON im Request-Body.", 400)
        data = {}
    if not isinstance(data, dict):
        raise ApiError("JSON-Objekt erwartet.", 400)
    return data


def int_arg(name, default=None, minimum=None, maximum=None):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(f"Parameter '{name}' muss eine Zahl sein.", 400)
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def paginate(query, serializer):
    page = int_arg("page", 1, minimum=1)
    per_page = int_arg(
        "per_page",
        current_app.config["DEFAULT_PER_PAGE"],
        minimum=1,
        maximum=current_app.config["MAX_PER_PAGE"],
    )
    total = query.order_by(None).count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "items": [serializer(i) for i in items],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }


_DE_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$")


def parse_date(value, field="Datum"):
    """Akzeptiert ISO (YYYY-MM-DD) und deutsches Format (TT.MM.JJJJ)."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    m = _DE_DATE.match(text)
    try:
        if m:
            day, month, year = (int(x) for x in m.groups())
            if year < 100:
                year += 2000 if year <= date.today().year % 100 else 1900
            return date(year, month, day)
        return date.fromisoformat(text[:10])
    except ValueError:
        raise ApiError(f"{field}: ungültiges Datum '{text}' (erwartet TT.MM.JJJJ oder JJJJ-MM-TT).", 400)


def csv_response(filename, header, rows):
    """CSV im Excel-freundlichen deutschen Format (Semikolon, UTF-8 mit BOM)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else _csv_value(v) for v in row])
    data = "﻿" + buf.getvalue()
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_value(value):
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value)
    if isinstance(value, bool):
        value = "ja" if value else "nein"
    text = str(value)
    # Schutz gegen CSV-/Formel-Injection beim Öffnen in Excel.
    if text and text[0] in "=+-@\t\r":
        text = "'" + text
    return text
