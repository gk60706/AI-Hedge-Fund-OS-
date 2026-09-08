"""V1.1 策略进化系统：淘汰低分策略，保留高分策略。"""


def evolve(strategies):
    alive = []
    for s in strategies:
        if s["score"] >= 80:
            alive.append(s)
    return alive
