"""Which product this deployment is.

Deliberately dependency-free: `app.core.config` imports it, and almost every
module imports the config. What each product *is* — its roles, its AI policy —
lives in `app.core.product_config`.
"""

from enum import StrEnum


class Product(StrEnum):
    """`PRODUCT` in the environment. One codebase, one deployment per product (D-077)."""

    #: The healthcare product ("Asclepius" to its users). The default: an
    #: environment that does not say otherwise behaves exactly as before.
    CAREBRIDGE = "carebridge"
    #: IP-SAKTI Sahayak — IP and regulatory information for Ayurvedic products.
    IP_SAKTI = "ip_sakti"
