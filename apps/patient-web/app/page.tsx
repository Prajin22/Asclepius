import { LandingPage } from "@/components/landing/LandingPage";
import { forProduct } from "@/components/product/ProductOnly";
import { SaktiLanding } from "@/components/sakti/SaktiLanding";

/** Public entry point. The product itself lives behind /login. One landing per product (D-077). */
export default forProduct({ carebridge: LandingPage, ip_sakti: SaktiLanding });
