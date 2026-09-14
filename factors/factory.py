from __future__ import annotations

from factors.value import (
    PEFactor,
    PBFactor,
    PSFactor,
)
from factors.momentum import (
    MomentumFactor,
    Momentum60Factor,
    Momentum120Factor,
)
from factors.quality import (
    ROEFactor,
    ROICFactor,
    RevenueGrowthFactor,
    ProfitGrowthFactor,
)
from factors.volatility import (
    VolatilityFactor,
)
from factors.liquidity import (
    TurnoverFactor,
    Amount20Factor,
)


class FactorFactory:
    @staticmethod
    def default_factors():
        return [
            PEFactor(),
            PBFactor(),
            PSFactor(),
            MomentumFactor(20),
            Momentum60Factor(),
            Momentum120Factor(),
            ROEFactor(),
            ROICFactor(),
            RevenueGrowthFactor(),
            ProfitGrowthFactor(),
            VolatilityFactor(20),
            TurnoverFactor(),
            Amount20Factor(),
        ]
