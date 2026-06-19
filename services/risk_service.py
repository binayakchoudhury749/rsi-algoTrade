def calculate_buy_targets(entry, stop_loss):
    risk = entry - stop_loss

    if risk <= 0:
        return None

    target_1 = entry + (risk * 3)
    target_2 = entry + (risk * 5)

    return {
        "risk": round(risk, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2)
    }


def calculate_sell_targets(entry, stop_loss):
    risk = stop_loss - entry

    if risk <= 0:
        return None

    target_1 = entry - (risk * 3)
    target_2 = entry - (risk * 5)

    return {
        "risk": round(risk, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2)
    }