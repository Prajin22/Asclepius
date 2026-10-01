"""What each product is: its name, the roles it accepts, its AI policy (D-077).

The single place the backend branches on the product. Everything else asks this
module, through the running application's `app.state.product_config`, rather
than comparing product names itself.
"""

from dataclasses import dataclass

from app.core.ai_policy import CAREBRIDGE_POLICY, IP_SAKTI_POLICY, AIPolicy
from app.core.product import Product
from app.models.enums import UserRole


@dataclass(frozen=True)
class ProductConfig:
    product: Product
    display_name: str
    #: Shown in the OpenAPI document.
    api_title: str
    api_description: str
    #: Roles this product's application accepts. An account holding any other
    #: role cannot sign in, and a token for one is refused (D-078).
    roles: frozenset[UserRole]
    ai_policy: AIPolicy

    def accepts(self, role: UserRole) -> bool:
        return role in self.roles


PRODUCTS: dict[Product, ProductConfig] = {
    Product.CAREBRIDGE: ProductConfig(
        product=Product.CAREBRIDGE,
        display_name="CareBridge",
        api_title="CareBridge API",
        api_description="Phase 1 foundation. Organises patient-provided information; does not diagnose or prescribe.",
        roles=frozenset({UserRole.PATIENT, UserRole.DOCTOR, UserRole.ADMIN}),
        ai_policy=CAREBRIDGE_POLICY,
    ),
    Product.IP_SAKTI: ProductConfig(
        product=Product.IP_SAKTI,
        display_name="IP-SAKTI Sahayak",
        api_title="IP-SAKTI Sahayak API",
        api_description=(
            "Intellectual property and regulatory information for Ayurvedic products. "
            "Provides information grounded in cited sources; does not give legal advice."
        ),
        roles=frozenset({UserRole.USER, UserRole.FACILITATOR, UserRole.CURATOR, UserRole.ADMIN}),
        ai_policy=IP_SAKTI_POLICY,
    ),
}


def product_config(product: Product) -> ProductConfig:
    return PRODUCTS[product]
