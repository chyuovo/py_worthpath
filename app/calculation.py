"""Decimal-only translation of the existing totals and trend formulas."""
from datetime import date,timedelta
from .common import *
def rate_at(rates,currency,base,day):
    if currency==base:return {"value":dec(1),"date":day,"source":"identity"}
    rows=[r for r in rates if r["currency"]==currency and r["baseCurrency"]==base and str(r["date"])[:10]<=day]
    if not rows:return None
    r=max(rows,key=lambda x:x["date"])
    return {"value":dec(r["rate"]),"date":str(r["date"])[:10],"source":r["source"]}
def revision_key(r):return (r["effectiveDate"],r.get("sequence",0))
def totals(positions,rates,base,day):
    assets=dec(0);liabilities=dec(0);missing=[];valuations=[];items=[]
    for p in positions:
        rows=[r for r in p["revisions"] if business_day(r["effectiveDate"])<=day]
        rev=max(rows,key=revision_key) if rows else None
        amount=dec(rev["amount"] if rev else 0);fx=rate_at(rates,p["currency"],base,day)
        included=p.get("included",True)
        if included and not fx and amount!=0 and p["currency"] not in missing:missing.append(p["currency"])
        pending=bool(p.get("metalType") and not rev and (not p.get("createdAt") or business_day(p["createdAt"])<=day))
        if pending and included:valuations.append({"id":p["id"],"name":p["name"]})
        converted=amount*fx["value"] if fx and not pending else None
        if converted is not None and included:
            if p["side"]=="asset":assets+=converted
            elif p["kind"]=="account" and converted<0:assets-=converted
            else:liabilities+=converted
        items.append(dict(id=p["id"],included=included,name=p["name"],kind=p["kind"],side=p["side"],currency=p["currency"],valuationAvailable=not pending,amount=fixed(amount),converted=fixed(converted,2) if converted is not None else None,rateDate=fx["date"] if fx else None,source=fx["source"] if fx else None))
    return dict(date=day,assets=fixed(assets,2),liabilities=fixed(liabilities,2),net=fixed(assets-liabilities,2),complete=not missing and not valuations,missingValuations=valuations,missing=missing,items=items)
def history_row(p,r,before=0):
    return dict(id=r["id"],sequence=r.get("sequence",0),createdAt=iso(r["createdAt"]) if r.get("createdAt") else None,positionId=p["id"],name=p["name"],kind=p["kind"],side=p["side"],currency=p["currency"],date=business_day(r["effectiveDate"]),time=business_time(r["effectiveDate"]),before=fixed(before),after=fixed(r["amount"]),delta=fixed(dec(r["amount"])-dec(before)),notes=r["notes"],reason=r["reason"])
def trend(positions,rates,base,start,end,grain="day"):
    positions=[p for p in positions if p.get("included",True)]
    dates=sorted(business_day(r["effectiveDate"]) for p in positions for r in p["revisions"])
    if not dates or dates[0]>end:return []
    start=max(start,dates[0]);day=date.fromisoformat(start);last=date.fromisoformat(end)
    previous=totals(positions,rates,base,(day-timedelta(days=1)).isoformat())
    balance=dec(0);exchange=dec(0);complete=True;output=[]
    while day<=last:
        ds=day.isoformat();value=totals(positions,rates,base,ds)
        if previous["complete"] and value["complete"]:
            revalued=dec(0)
            for item in previous["items"]:
                if not item["included"]:continue
                fx=rate_at(rates,item["currency"],base,ds)
                v=dec(item["amount"])*(fx["value"] if fx else dec(0))
                revalued+=v if item["side"]=="asset" else -v
            exchange+=revalued-dec(previous["net"]);balance+=dec(value["net"])-revalued
        else:complete=False
        previous=value;next_day=day+timedelta(days=1)
        if grain=="day" or day==last or (grain=="week" and next_day.weekday()==0) or (grain=="month" and next_day.day==1):
            value.pop("items")
            output.append({**value,"balanceChange":fixed(balance,2) if complete else None,"fxChange":fixed(exchange,2) if complete else None})
            balance=dec(0);exchange=dec(0);complete=True
        day=next_day
    return output
def movement_deltas(operation,amount,received,fee,source_side="asset",target_side="asset"):
    principal=dec(amount);charge=dec(fee);debt=dec(received)
    if operation=="transfer":return (principal+charge)*(1 if source_side=="liability" else -1),debt*(-1 if target_side=="liability" else 1),"transfer_out","transfer_in"
    incoming=operation in ("borrow","collect")
    if incoming and charge>principal:fail("收款手续费不能超过收款金额")
    return principal-charge if incoming else -(principal+charge),debt if operation in ("borrow","lend") else -debt,"loan_"+operation,"loan_"+operation
