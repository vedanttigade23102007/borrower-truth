"""The tables a borrower's own spreadsheet can be mapped onto, column by column.

Each column says what type the checks expect (the same types the generator writes), how a lender's value is
converted, and the names lenders commonly give it. The names are ordinary lending vocabulary, written before the
mapper was tried on any real lender layout; `negatives` are words that mean a different number with a similar name
("original balance" is not the current balance).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pyarrow as pa


@dataclass(frozen=True)
class Col:
    name: str
    type: pa.DataType
    kind: str  # text | id | month | money | int | rate | dpd | bool | flag | date_split | terms
    required: bool = False
    synonyms: tuple[str, ...] = ()
    negatives: tuple[str, ...] = ()
    outputs: tuple[str, ...] = field(default=())  # for a column that fills more than one (a date -> month and day)


MONTH_SYN = ("reporting period", "report date", "as of date", "as of", "period end date", "period end", "reporting date",
             "cutoff date", "cut off date", "period ending", "statement date")
# a code, a flag or a date is never an amount; an amount or a code is never a date
NOT_AMOUNT = ("code", "date", "indicator", "type", "flag", "rate", "percent", "count")
NOT_DATE = ("amount", "balance", "rate", "number", "code", "indicator", "count", "percent", "flag", "type")
DATE_NEG = ("origination", "original", "maturity", "first payment", "next payment", "last payment", "paid off",
            "zero") + NOT_DATE
BAL_NEG = ("original", "beginning", "begin", "opening", "scheduled", "charged", "chargeoff", "prior", "previous",
           "value", "payment", "paid", "recovered", "recovery") + NOT_AMOUNT
DPD_SYN = ("days past due", "days delinquent", "delinquency status", "dpd", "days late", "delinquency",
           "aging bucket", "delinquency bucket", "past due days", "past due")

TAPE = (
    Col("month", pa.int16(), "month", True, MONTH_SYN, DATE_NEG),
    Col("facility_id", pa.string(), "text", True, ("facility", "facility id", "credit line", "facility number")),
    Col("borrower_id", pa.string(), "text", True, ()),  # set once per lender, not read from the file
    Col("asset_id", pa.string(), "id", True, ("loan number", "loan id", "loan no", "account number", "account no",
                                             "asset number", "asset id", "contract number", "contract id")),
    Col("vin", pa.string(), "text", True, ("vin", "vehicle identification number", "serial number", "vehicle id")),
    Col("obligor_id", pa.string(), "id", True, ("customer number", "customer id", "obligor id", "obligor number",
                                               "client id", "client number", "consumer id")),
    Col("balance", pa.float32(), "money", True, ("current balance", "principal balance", "current principal balance",
                                                 "unpaid principal balance", "upb", "outstanding balance",
                                                 "outstanding principal", "ending balance", "end balance", "balance"),
        BAL_NEG),
    Col("dpd_bucket_reported", pa.int8(), "dpd", True, DPD_SYN, ("true", "servicer", "worst", "max", "ever")),
    Col("deferred_flag", pa.int8(), "flag", True, ("deferred", "deferral", "deferment", "deferral flag",
                                                   "deferred flag", "payment deferral", "forbearance")),
    Col("eligible_reported", pa.bool_(), "bool", True, ("eligible", "eligibility", "eligible flag",
                                                        "borrowing base eligible", "eligibility status")),
    Col("orig_month", pa.int16(), "month", False, ("origination date", "funded date", "funding date", "open date",
                                                   "note date", "loan date", "contract date", "origination month"),
        NOT_DATE),
    Col("orig_amount", pa.float64(), "money", False, ("original amount", "original balance", "original principal",
                                                      "original loan amount", "amount financed", "loan amount",
                                                      "funded amount"),
        ("current", "ending", "end", "outstanding", "unpaid") + NOT_AMOUNT),
    Col("rate", pa.float64(), "rate", False, ("interest rate", "rate", "apr", "note rate", "coupon", "contract rate",
                                              "annual percentage rate")),
    Col("term", pa.int16(), "int", False, ("term", "original term", "term months", "loan term", "term in months")),
    Col("make", pa.string(), "text", False, ("make", "vehicle make", "manufacturer")),
    Col("model", pa.string(), "text", False, ("model", "vehicle model", "model name"), ("year",)),
    Col("model_year", pa.int16(), "int", False, ("model year", "vehicle year", "year")),
    Col("obligor_state", pa.string(), "text", False, ("state", "obligor state", "customer state", "borrower state",
                                                      "state code")),
    Col("credit_score", pa.int16(), "int", False, ("credit score", "fico", "fico score", "score", "bureau score"),
        ("type", "date", "model")),
)

SOURCE_TRUTH = (
    Col("month", pa.int16(), "month", True, MONTH_SYN, DATE_NEG),
    Col("borrower_id", pa.string(), "text", True, ()),
    Col("asset_id", pa.string(), "id", True, TAPE[3].synonyms),
    Col("dpd_bucket_true", pa.int8(), "dpd", True, DPD_SYN, ("reported", "worst", "max", "ever")),
    Col("balance_true", pa.float32(), "money", True, TAPE[6].synonyms, BAL_NEG),
)

INVOICES = (
    Col("borrower_id", pa.string(), "text", True, ()),
    Col("invoice_id", pa.string(), "id", False, ("record id", "line id", "row id", "invoice id", "record number")),
    Col("facility_id", pa.string(), "text", True, ("facility", "facility id", "credit line", "facility number")),
    Col("pledged_month", pa.int64(), "month", True, ("report date", "as of date", "pledge date", "pledged date",
                                                    "schedule date", "borrowing base date", "submitted date"),
        ("invoice", "issue", "due") + NOT_DATE),
    Col("invoice_number", pa.string(), "id", True, ("invoice number", "invoice no", "invoice", "inv no",
                                                   "document number", "invoice num")),
    Col("po_number", pa.string(), "id", False, ("po number", "po", "purchase order", "purchase order number",
                                                "customer po")),
    Col("debtor_id", pa.string(), "id", True, ("customer number", "customer id", "debtor id", "debtor number",
                                              "customer no", "account number")),
    Col("debtor_name", pa.string(), "text", True, ("customer name", "debtor name", "customer", "bill to",
                                                  "account name", "debtor")),
    Col("issue_date", pa.int64(), "date_split", True, ("invoice date", "issue date", "billing date", "date",
                                                       "document date"), ("due", "report", "pledge", "as of") + NOT_DATE,
        outputs=("issue_month", "issue_day")),
    Col("due_days", pa.int64(), "terms", True, ("terms", "payment terms", "due days", "net days", "terms days")),
    Col("amount", pa.float64(), "money", True, ("amount", "invoice amount", "open amount", "face amount",
                                                "invoice total", "total amount", "original amount"),
        ("paid", "tax", "discount", "credit", "number") + NOT_AMOUNT),
    Col("description", pa.string(), "text", False, ("description", "goods", "memo", "item", "product", "details")),
)

TABLES = {"tape": TAPE, "source_truth": SOURCE_TRUTH, "invoices": INVOICES}
# the column a reporting month is read from, the amount a control total adds up, and what makes a row unique
MONTH_COL = {"tape": "month", "source_truth": "month", "invoices": "pledged_month"}
AMOUNT_COL = {"tape": "balance", "source_truth": "balance_true", "invoices": "amount"}
KEY = {"tape": ("facility_id", "asset_id", "month"), "source_truth": ("asset_id", "month"),
       "invoices": ("facility_id", "invoice_number", "pledged_month")}
ID_COL = {"tape": "asset_id", "source_truth": "asset_id", "invoices": "invoice_number"}


def out_schema(table: str) -> pa.Schema:
    fields = []
    for c in TABLES[table]:
        if c.outputs:
            fields += [pa.field(o, c.type) for o in c.outputs]
        else:
            fields.append(pa.field(c.name, c.type))
    return pa.schema(fields)
