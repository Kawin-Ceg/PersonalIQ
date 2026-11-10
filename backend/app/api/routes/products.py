from collections import Counter
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.user import current_user
from app.core.database import get_session
from app.models import User
from app.schemas.catalog import CatalogResponse, CategoryCount, product_out
from app.schemas.commerce import CartPlan, CartRequest, ExcludedProduct, NeedOption, RankedProduct, RankingResponse
from app.services.cart import optimize_cart
from app.services.catalog import category_counts, search_products
from app.services.personal_intelligence import build_user_context
from app.services.ranking import need_of, rank_products

router = APIRouter(tags=["products"])


@router.get("/products", response_model=CatalogResponse)
def list_products(
    category: str | None = Query(None),
    q: str | None = Query(None, max_length=100),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> CatalogResponse:
    items = search_products(session, category=category, q=q)
    return CatalogResponse(
        items=[product_out(p, user.currency) for p in items],
        total=len(items),
        categories=[CategoryCount(category=c, count=n) for c, n in category_counts(session)],
    )


@router.get("/products/ranked", response_model=RankingResponse)
def ranked_products(
    category: str | None = Query(None),
    need: str | None = Query(None),
    max_price: Decimal | None = Query(None, gt=0, description="In the user's currency"),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> RankingResponse:
    """Catalog ranked for the current user, with the score breakdown and anything left out."""
    products = search_products(session, category=category)
    if need:
        products = [p for p in products if need_of(p) == need]
    ctx = build_user_context(session, user)
    ranking = rank_products(session, products, ctx, max_price=max_price)
    return RankingResponse(
        weights=ctx.scoring_weights,
        ranked=[
            RankedProduct(product=product_out(s.product, ctx.currency), score=s.score, rank=s.rank, components=s.components)
            for s in ranking.ranked
        ],
        excluded=[ExcludedProduct(product=product_out(p, ctx.currency), reasons=r) for p, r in ranking.excluded],
    )


@router.get("/products/needs", response_model=list[NeedOption])
def needs(session: Session = Depends(get_session)) -> list[NeedOption]:
    products = search_products(session)
    counts = Counter((need_of(p), p.category) for p in products)
    return [NeedOption(need=n, category=c, count=k) for (n, c), k in sorted(counts.items(), key=lambda kv: (kv[0][1], kv[0][0]))]


@router.post("/cart/optimize", response_model=CartPlan)
def build_cart(req: CartRequest, user: User = Depends(current_user), session: Session = Depends(get_session)) -> CartPlan:
    ctx = build_user_context(session, user)
    return optimize_cart(session, search_products(session), ctx, req)
