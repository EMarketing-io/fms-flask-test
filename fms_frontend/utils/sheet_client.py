from typing import Dict, List


def get_client_list(dropdown_ws) -> List[str]:
    values = dropdown_ws.col_values(6)[:101]
    return [v.strip() for v in values if v and v.strip()]


def get_employee_email_map(dropdown_ws) -> Dict[str, str]:
    names = dropdown_ws.col_values(1)[:30]
    emails = dropdown_ws.col_values(4)[:30]
    out: Dict[str, str] = {}
    for i in range(max(len(names), len(emails))):
        name = (names[i] if i < len(names) else "").strip()
        email = (emails[i] if i < len(emails) else "").strip()
        if name:
            out[name] = email
    return out


def append_main_row_in_order(main_ws, row: List[str]) -> None:
    main_ws.append_row(row, value_input_option="USER_ENTERED")