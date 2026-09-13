from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from carda_link.assistant.models import ChatQueryLog
from carda_link.assistant.services.chatbot_service import ChatbotService
from carda_link.auctions.models import Auction, Bid, Lot
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.invoicing.models import Invoice
from carda_link.users.models import User, Watchlist

logger = logging.getLogger(__name__)

chatbot_service = ChatbotService()


def _format_seller_query(user: User, question_lower: str) -> dict[str, Any] | None:
    """Check if query is asking for seller-specific operational data."""
    # 1. Harvest Batches
    if any(k in question_lower for k in ["batch", "harvest", "quality", "reject"]):
        batches = HarvestBatch.objects.filter(estate__owner=user).select_related("estate").order_by("-created_at")[:6]
        if not batches.exists():
            return {
                "category": "Farm Operations",
                "answer": "You have not registered any harvest batches yet. Go to **Harvest Batches** on your dashboard to log your first cardamom batch for quality grading.",
                "suggestions": ["How do I log a harvest batch?", "Show my registered estates", "Pest control advice"],
            }
        lines = ["**Your Recent Harvest Batches:**\n"]
        for b in batches:
            grade_badge = f"`{b.grade}`" if b.grade != "UNGRADED" else "*Pending Grading*"
            status_desc = "❌ Rejected" if b.is_rejected else ("⏳ Pending Grading" if b.grade == "UNGRADED" else f"✅ Graded ({b.get_grade_display()})")
            line = f"• **Batch #{b.id}** ({b.estate.name}) — {b.weight_kg} kg | Grade: {grade_badge} | Status: **{status_desc}**"
            if b.is_rejected and b.rejection_reason:
                line += f"\n  ↳ *Rejection reason:* {b.rejection_reason}"
            lines.append(line)
        return {
            "category": "Harvest Inventory",
            "answer": "\n".join(lines),
            "suggestions": ["Show my live auction lots", "My cardamom estates", "How do I improve cardamom grade?"],
        }

    # 2. Estates
    if any(k in question_lower for k in ["estate", "farm", "plantation", "acres"]):
        estates = Estate.objects.filter(owner=user).order_by("-created_at")
        if not estates.exists():
            return {
                "category": "Estates",
                "answer": "You do not have any registered estates yet. You can add your cardamom plantation under **My Estates**.",
                "suggestions": ["How to register an estate?", "Batch quality standards", "Cardamom pricing"],
            }
        lines = ["**Your Registered Cardamom Estates:**\n"]
        for e in estates:
            batch_count = e.harvest_batches.count()
            lines.append(f"• **{e.name}** — {e.location} ({e.area_in_acres} Acres, {batch_count} batches logged)")
        return {
            "category": "Estates",
            "answer": "\n".join(lines),
            "suggestions": ["What is the status of my harvest batches?", "Show my live auction lots", "Cardamom cultivation tips"],
        }

    # 3. Lots & Auction Sales
    if any(k in question_lower for k in ["lot", "auction", "sale", "earning", "payout"]):
        lots = Lot.objects.filter(harvest_batch__estate__owner=user).select_related("auction", "harvest_batch").order_by("-created_at")[:6]
        if not lots.exists():
            return {
                "category": "Auction Lots",
                "answer": "None of your approved batches are currently assigned to auction lots. Once the admin assigns your verified batches to an upcoming auction, they will appear here.",
                "suggestions": ["What is the status of my harvest batches?", "My cardamom estates", "How do cardamom auctions work?"],
            }
        lines = ["**Your Cardamom Auction Lots:**\n"]
        for l in lots:
            high_bid_str = f"₹{l.highest_bid_per_kg}/kg" if l.highest_bid_per_kg else "No bids yet"
            sold_str = " (SOLD)" if l.is_sold else ""
            lines.append(f"• **Lot #{l.lot_number}** ({l.harvest_batch.grade}, {l.harvest_batch.weight_kg} kg) — Base: ₹{l.base_price_per_kg}/kg | Top Bid: **{high_bid_str}** | Auction: {l.auction.get_status_display()}{sold_str}")
        return {
            "category": "Auction Lots",
            "answer": "\n".join(lines),
            "suggestions": ["Earnings and payouts summary", "What is the status of my harvest batches?", "Auction schedule"],
        }

    return None


def _format_buyer_query(user: User, question_lower: str) -> dict[str, Any] | None:
    """Check if query is asking for buyer-specific operational data."""
    # 1. Bids & Leading / Outbid status
    if any(k in question_lower for k in ["bid", "leading", "outbid", "offer"]):
        bids = Bid.objects.filter(bidder=user).select_related("lot__auction", "lot__harvest_batch").order_by("-timestamp")[:6]
        if not bids.exists():
            return {
                "category": "Live Bidding",
                "answer": "You haven't placed any bids yet. Visit **Live Auctions** to browse lots and place bids.",
                "suggestions": ["Show active cardamom auctions", "My starred lots", "Cardamom grade guide"],
            }
        lines = ["**Your Recent Auction Bids:**\n"]
        for b in bids:
            lot = b.lot
            is_top = (lot.highest_bid_per_kg is not None and b.amount_per_kg == lot.highest_bid_per_kg)
            if lot.auction.status == "COMPLETED" or lot.is_sold:
                status_label = "🏆 WON" if is_top else "❌ Lost"
            elif lot.auction.status == "ACTIVE":
                status_label = "🟢 LEADING" if is_top else "🔴 OUTBID"
            else:
                status_label = "⏳ Pending"

            lines.append(f"• **Lot #{lot.lot_number}** ({lot.harvest_batch.grade}): Your bid ₹{b.amount_per_kg}/kg — Status: **{status_label}**")
        return {
            "category": "Live Bidding",
            "answer": "\n".join(lines),
            "suggestions": ["Show active cardamom auctions", "Do I have unpaid invoices?", "My starred lots"],
        }

    # 2. Watchlist
    if any(k in question_lower for k in ["watch", "starred", "saved"]):
        watchlist = Watchlist.objects.filter(buyer=user).select_related("lot__auction", "lot__harvest_batch").order_by("-created_at")[:6]
        if not watchlist.exists():
            return {
                "category": "Watchlist",
                "answer": "Your watchlist is currently empty. Star lots in **Live Auctions** to monitor them in real-time.",
                "suggestions": ["Show active cardamom auctions", "What is my current bid status?", "Pricing trends"],
            }
        lines = ["**Your Starred Lots Watchlist:**\n"]
        for item in watchlist:
            lot = item.lot
            high_str = f"₹{lot.highest_bid_per_kg}/kg" if lot.highest_bid_per_kg else "No bids"
            lines.append(f"• **Lot #{lot.lot_number}** ({lot.harvest_batch.grade}, {lot.harvest_batch.weight_kg} kg) — Base: ₹{lot.base_price_per_kg}/kg | High Bid: **{high_str}** | Auction: {lot.auction.get_status_display()}")
        return {
            "category": "Watchlist",
            "answer": "\n".join(lines),
            "suggestions": ["What is my current bid status?", "Show active cardamom auctions", "Pending invoices"],
        }

    # 3. Won Lots
    if any(k in question_lower for k in ["won", "winner", "purchased"]):
        candidate_lots = Lot.objects.filter(is_sold=True).prefetch_related("bids").select_related("auction", "harvest_batch")
        won_lots = []
        for l in candidate_lots:
            top_bid = l.bids.order_by("-amount_per_kg").first()
            if top_bid and top_bid.bidder == user:
                won_lots.append((l, top_bid))

        if not won_lots:
            return {
                "category": "Won Lots",
                "answer": "You have not won any cardamom lots yet. Keep bidding in **Live Auctions**!",
                "suggestions": ["Show active cardamom auctions", "What is my current bid status?", "Inspection standards"],
            }
        lines = ["**Cardamom Lots You Have Won:**\n"]
        for lot, top_bid in won_lots[:6]:
            total = round(lot.harvest_batch.weight_kg * top_bid.amount_per_kg, 2)
            lines.append(f"• **Lot #{lot.lot_number}** ({lot.harvest_batch.grade}, {lot.harvest_batch.weight_kg} kg) — Winning Bid: ₹{top_bid.amount_per_kg}/kg (Total: ₹{total})")
        return {
            "category": "Won Lots",
            "answer": "\n".join(lines),
            "suggestions": ["Do I have unpaid invoices?", "Show active cardamom auctions", "Download sale certificate"],
        }

    # 4. Invoices & Payments
    if any(k in question_lower for k in ["invoice", "payment", "bill", "unpaid", "pending invoice"]):
        invoices = Invoice.objects.filter(buyer=user).order_by("-issued_at")[:6]
        if not invoices.exists():
            return {
                "category": "Invoices",
                "answer": "You do not have any invoices issued yet.",
                "suggestions": ["Show active cardamom auctions", "What is my current bid status?", "My starred lots"],
            }
        unpaid = [inv for inv in invoices if inv.status == "PENDING"]
        paid = [inv for inv in invoices if inv.status == "PAID"]
        lines = [f"**Your Invoices Overview:**\nYou have **{len(unpaid)} unpaid** and **{len(paid)} settled** invoices.\n"]
        for inv in invoices:
            status_badge = "🔴 PENDING" if inv.status == "PENDING" else "🟢 PAID"
            lines.append(f"• **Invoice #{inv.id}** — ₹{inv.total_amount} | Status: **{status_badge}**")
        return {
            "category": "Invoices",
            "answer": "\n".join(lines),
            "suggestions": ["What is my current bid status?", "Show active cardamom auctions", "Help with payment verification"],
        }

    return None


def _format_admin_query(user: User, question_lower: str) -> dict[str, Any] | None:
    """Check if query is asking for platform administrative statistics."""
    if any(k in question_lower for k in ["pending", "approval", "ungraded", "verification", "platform", "stat"]):
        pending_users = User.objects.filter(status=User.Status.PENDING).count()
        ungraded_batches = HarvestBatch.objects.filter(grade="UNGRADED", is_rejected=False).count()
        active_auctions = Auction.objects.filter(status="ACTIVE").count()
        pending_invoices = Invoice.objects.filter(status="PENDING").count()

        lines = [
            "**CardaLink Platform Status Summary:**\n",
            f"• **Pending User Registrations:** {pending_users} waiting for KYC review",
            f"• **Ungraded Harvest Batches:** {ungraded_batches} in quality inspection queue",
            f"• **Active Auctions:** {active_auctions} running right now",
            f"• **Pending Settlement Invoices:** {pending_invoices} awaiting payment verification",
        ]
        return {
            "category": "Platform Administration",
            "answer": "\n".join(lines),
            "suggestions": ["Review pending registrations", "Grade harvest batches", "Manage auctions"],
        }
    return None


@require_POST
@login_required
def assistant_query_view(request: HttpRequest) -> JsonResponse:
    """
    Authenticated role-aware AI Assistant endpoint.
    Strictly queries request.user's isolated data (zero cross-user leakage).
    Logs interaction to ChatQueryLog.
    """
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        message = body.get("message", "").strip()
    except Exception:
        message = request.POST.get("message", "").strip()

    if not message:
        return JsonResponse({
            "status": "error",
            "category": "Error",
            "answer": "Please provide a valid question or message.",
            "suggestions": [],
        }, status=400)

    question_lower = message.lower()
    user = request.user
    role = getattr(user, "role", "")
    response_data: dict[str, Any] | None = None

    # Role-based context checks
    if role == User.Role.SELLER:
        response_data = _format_seller_query(user, question_lower)
    elif role == User.Role.BUYER:
        response_data = _format_buyer_query(user, question_lower)
    elif role == User.Role.ADMIN or user.is_staff or user.is_superuser:
        response_data = _format_admin_query(user, question_lower)

    # If not handled by role-specific handler, query the domain ChatbotService
    if not response_data:
        try:
            domain_res = chatbot_service.get_response(message)
            response_data = {
                "category": domain_res.get("category", "General"),
                "answer": domain_res.get("answer", "I could not find an answer to that question."),
                "suggestions": domain_res.get("suggestions", []),
            }
        except Exception as err:
            logger.error("Domain chatbot service failed: %s", err, exc_info=True)
            response_data = {
                "category": "Assistant",
                "answer": "I'm currently unable to answer that question. Please try asking about your batches, bids, auctions, or cardamom cultivation advice.",
                "suggestions": ["Pest control tips", "Cardamom harvesting advice", "Live auction schedule"],
            }

    # Log interaction to ChatQueryLog
    try:
        ChatQueryLog.objects.create(
            user=user,
            query_text=message,
            response_text=response_data["answer"],
        )
    except Exception as log_err:
        logger.error("Failed to log chat query to database: %s", log_err)

    return JsonResponse({
        "status": "ok",
        "category": response_data.get("category", "Assistant"),
        "answer": response_data.get("answer", ""),
        "suggestions": response_data.get("suggestions", []),
    })
