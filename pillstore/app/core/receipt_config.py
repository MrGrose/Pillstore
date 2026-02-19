RECEIPT_TITLE = "PillStore — товарный чек"
RECEIPT_META = [
    ("id", "Заказ #"),
    ("created_at", "Дата"),
    ("contact_phone", "Тел."),
    ("user_email", "Клиент"),
]
RECEIPT_TABLE_COLUMNS = [
    ("name", "Товар", None),
    ("quantity", "Кол.", None),
    ("unit_price", "Цена", "%.2f"),
    ("total_price", "Сумма", "%.2f"),
]
RECEIPT_TOTAL_LABEL = "Итого"
RECEIPT_TOTAL_FIELD = "total_amount"
RECEIPT_TOTAL_FORMAT = "%.2f"
RECEIPT_FOOTER = "Спасибо за заказ!"


def build_receipt_meta(order) -> list[tuple[str, str]]:
    out = []
    for key, label in RECEIPT_META:
        if key == "id":
            out.append((label + str(getattr(order, "id", "")), ""))
        elif key == "created_at":
            dt = getattr(order, "created_at", None)
            out.append((label + ":", dt.strftime("%d.%m.%Y %H:%M") if dt else ""))
        elif key == "contact_phone":
            v = getattr(order, "contact_phone", None)
            if v:
                out.append((label + ":", v))
        elif key == "user_email":
            user = getattr(order, "user", None)
            if user:
                out.append((label + ":", getattr(user, "email", "")))
        else:
            v = getattr(order, key, None)
            if v:
                out.append((label + ":", str(v)))
    return out


def build_receipt_table(order) -> tuple[list[str], list[list]]:
    headers = [col[1] for col in RECEIPT_TABLE_COLUMNS]
    rows = []
    for item in order.items:
        product = getattr(item, "product", None)
        row = []
        for col_key, _col_label, fmt in RECEIPT_TABLE_COLUMNS:
            if col_key == "name":
                val = product.name if product else ""
            elif col_key in ("quantity", "unit_price", "total_price"):
                val = getattr(item, col_key, "")
            else:
                val = getattr(item, col_key, "") or (
                    getattr(product, col_key, "") if product else ""
                )
            if fmt and isinstance(val, (int, float)):
                val = fmt % val
            elif isinstance(val, (int, float)) and not fmt:
                val = str(val)
            row.append(val)
        rows.append(row)
    return headers, rows


def build_receipt_total(order) -> str:
    val = getattr(order, RECEIPT_TOTAL_FIELD, 0)
    if isinstance(val, (int, float)):
        return RECEIPT_TOTAL_FORMAT % val
    return str(val)
