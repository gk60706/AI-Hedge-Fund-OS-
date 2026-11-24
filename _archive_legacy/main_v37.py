from datetime import date

from data.universe import (
    HistoricalUniverse,
    SecurityLifecycle,
)
from data.point_in_time import (
    PITRecord,
    PointInTimeStore,
)
from validation.audit import (
    BacktestAudit,
)


def main():
    print(
        "\n=============================="
    )
    print(
        "AI Hedge Fund OS V3.7"
    )
    print(
        "Point-in-Time & Bias Control"
    )
    print(
        "==============================\n"
    )
    # ==================================
    # 1. Historical Universe
    # ==================================
    universe = HistoricalUniverse()
    universe.add(
        SecurityLifecycle(
            code="300394",
            ipo_date=date(2016, 1, 1,),
            name="天孚通信",
        )
    )
    universe.add(
        SecurityLifecycle(
            code="600000",
            ipo_date=date(1999, 11, 10,),
            name="浦发银行",
        )
    )
    # ==================================
    # 2. Point In Time
    # ==================================
    store = PointInTimeStore()
    store.add(
        PITRecord(
            code="300394",
            period_end=date(2023, 12, 31,),
            value=100,
            publish_date=date(2024, 3, 28,),
        )
    )
    # ==================================
    # 3. 查询
    # ==================================
    record_before = store.query(
        code="300394",
        as_of_date=date(2024, 3, 1,),
    )
    record_after = store.query(
        code="300394",
        as_of_date=date(2024, 4, 1,),
    )
    print(
        "2024-03-01 可用数据:",
        record_before,
    )
    print(
        "2024-04-01 可用数据:",
        record_after,
    )
    # ==================================
    # 4. Audit
    # ==================================
    audit = BacktestAudit(universe)
    universe_result = (
        audit.audit_universe(
            codes=[
                "300394",
                "600000",
            ],
            as_of_date=date(2024, 1, 10,),
        )
    )
    print(
        "\n===== AUDIT ====="
    )
    print(universe_result)


if __name__ == "__main__":
    main()
