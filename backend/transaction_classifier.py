"""
Transaction Nature & Ledger Group Classifier
Provides deterministic Indian bank transaction classification into Miracle/Tally ledger groups.
Cleaned up duplicate STATUTORY_TAX and BANK_CHARGE keyword steps (Issues #6 & #7).
"""

def classify_transaction_nature(
    narr: str, party_name: str = "", amount: float = 0.0, tx_type: str = "Payment"
) -> str:
    """
    Classifies a bank transaction into standard Indian Accounting (Miracle/Tally) ledger groups.
    Determines group via deterministic heuristics based on narration keywords, payment/receipt direction,
    and transaction amount range.
    """
    text = f"{narr} {party_name}".strip().upper()
    narr_up = narr.strip().upper()
    is_payment = tx_type.strip().capitalize() in ("Payment", "Debit", "Dr", "Out")
    is_receipt = not is_payment

    # AMOUNT RANGE SIGNALS
    amt = abs(float(amount or 0))
    is_small_amt = amt < 5000  # petty cash / food / cab / recharge
    is_medium_amt = 5000 <= amt < 50000  # salary / vendor / utility
    is_large_amt = amt >= 50000  # EMI / bulk salary / investment / bank transfer
    is_round_amt = amt > 0 and amt % 500 == 0 and amt == int(amt)

    # ── STEP 0-CASH: CASH MOVEMENTS ──────────────────────────────────────────
    CASH_MOVEMENT_KWS = [
        "CASH RECEIVED",
        "CASH REC",
        "CASH RECVD",
        "CASH RECIEVED",
        "CASH DEPOSIT",
        "CASH DEPO",
        "CASH PAID",
        "CASH CHQ",
        "CASH CHEQUE",
        "CASH WITHDRAWAL",
        "CASH WITHDR",
        "ATM CASH",
        "BY CASH",
        "TO CASH",
    ]
    if any(k in text for k in CASH_MOVEMENT_KWS) or party_name.upper() in (
        "CASH",
        "CASH RECEIVED",
        "CASH ACCOUNT",
        "CASH A/C",
        "CASH IN HAND",
    ):
        return "Cash in Hand"

    # ── STEP 0: BANK CHARGES & FEES (Top Priority Expense) ───────────────────
    BANK_CHARGE_KWS = [
        "BANK CHARGES",
        "BANK CHAGES",
        "BANK CHARG",
        "BANK CHAG",
        "MDR RCVRY",
        "RUPAY MDR",
        "INSTAALERT",
        "INSTAALERTCHG",
        "ALERTCHG",
        "SMS CHG",
        "SMS-CHARG",
        "SMS CHARGE",
        "MIN BAL",
        "ATM CHG",
        "DEBIT CARD CHG",
        "CHQ BOUNCE",
        "DEPOSITORY CHARGES",
        "PROCESSING FEE",
        "LATE FEE",
        "PENALTY",
        "FORECLOSURE",
        "POS RENTAL",
        "SOUND BOX",
        "SERVICE CHG",
        "SERVICE CHARGE",
        "SERVICE CHARGES",
        "NACH CHARGE",
        "ECS CHARGE",
    ]
    if any(k in text for k in BANK_CHARGE_KWS):
        return "Indirect Expenses"

    # ── STEP 1: NARRATION PREFIX SIGNALS ────────────────────────────────
    if narr_up.startswith(("ACH D", "NACH D", "ECS D", "MANDATE DR")):
        is_payment = True
        is_receipt = False
    if narr_up.startswith(
        ("NEFT CR", "IMPS CR", "UPI CR", "ACH CR", "NACH CR", "ECS CR")
    ):
        is_receipt = True
        is_payment = False

    # ── STEP 2: AMOUNT + DIRECTION COMBINED SIGNALS ─────────────────────
    if is_payment and is_round_amt and is_large_amt:
        if any(
            k in text
            for k in [
                "EMI",
                "LOAN",
                "HOUSING",
                "HOME LOAN",
                "PERSONAL LOAN",
                "AUTO LOAN",
                "VEHICLE",
            ]
        ):
            return "Secured Loans"
        if any(
            k in text
            for k in ["SIP", "INVEST", "MUTUAL FUND", "GROWW", "ZERODHA", "UPSTOX"]
        ):
            return "Investments"

    if is_receipt and is_large_amt and is_round_amt:
        if any(k in text for k in ["SALARY", "PAYROLL", "COMPENSATION"]):
            return "Indirect Income"
        if any(k in text for k in ["LOAN", "DISBURS", "OD LIMIT", "OVERDRAFT"]):
            return "Secured Loans"

    # ── STEP 2b: STATUTORY TAXES & GOVT DUTIES (Top Priority) ───────────
    STATUTORY_TAX_KWS = [
        "PROFESSIONAL TAX",
        "PTAX",
        "GST",
        "CGST",
        "SGST",
        "IGST",
        "TDS",
        "TCS",
        "ADVANCE TAX",
        "INCOME TAX",
        "DUTIES & TAXES",
        "CHALLAN",
        "GSTPMT",
        "NSDL",
        "TRACES",
        "TAX PAYMENT",
        "TDS PAYMENT",
    ]
    if any(k in text for k in STATUTORY_TAX_KWS):
        return "Duties & Taxes"

    # ── STEP 3: INVESTMENT PLATFORMS & CLEARING CORPS ───────────────────
    INVESTMENT_KWS = [
        "GROWW",
        "NEXTBILLION",
        "ZERODHA",
        "UPSTOX",
        "ANGEL ONE",
        "ANGELBROKING",
        "PAYTM MONEY",
        "ICICI DIRECT",
        "MOTILAL OSWAL",
        "INDIAN CLEARING",
        "INDIAN CLEARING CORP",
        "CLEARING CORP",
        "NSCCL",
        "BSCCL",
        "ICCL",
        "NSE CLEARING",
        "BSE CLEARING",
        "MUTUAL FUND",
        "SHARES",
        "SECURITIES",
        "DEMAT",
        "SMALLCASE",
        "KUVERA",
        "FYERS",
        "DHANI STOCKS",
    ]
    if any(k in text for k in INVESTMENT_KWS):
        return "Investments"

    # ── STEP 5: CREDIT CARD GATEWAYS ────────────────────────────────────
    CREDIT_CARD_GATEWAY_KWS = [
        "CRED",
        "CRED CLUB",
        "RAZORPAY",
        "PAYTM GATEWAY",
        "INSTAMOJO",
        "BILLDESK",
        "CCAVENUE",
        "PAYU",
        "EASEBUZZ",
        "CASHFREE",
    ]
    if any(k in text for k in CREDIT_CARD_GATEWAY_KWS):
        return "Indirect Expenses" if is_payment else "Indirect Income"

    # ── STEP 6: BANKS & FINANCIAL INSTITUTIONS ───────────────────────────
    BANK_FINANCE_KWS = [
        "IDFC FIRST BANK",
        "IDFCFIRST",
        "HDFC BANK",
        "ICICI BANK",
        "AXIS BANK",
        "STATE BANK OF INDIA",
        "SBI ",
        "KOTAK MAHINDRA",
        "INDUSIND BANK",
        "BANK OF BARODA",
        "PUNJAB NATIONAL BANK",
        "CANARA BANK",
        "UNION BANK",
        "FINANCIAL SERVICES",
        "BANDHAN BANK",
        "YES BANK",
        "RBL BANK",
        "FEDERAL BANK",
        "KARNATAKA BANK",
    ]
    if "SBIMOPS" in text or "MOPS" in text:
        return "Indirect Expenses"

    if any(k in text for k in BANK_FINANCE_KWS):
        p_upper = (party_name or "").upper().strip()
        is_real_bank = (
            any(
                b in p_upper
                for b in [
                    "HDFC BANK",
                    "ICICI BANK",
                    "STATE BANK",
                    "SBI A/C",
                    "AXIS BANK",
                    "KOTAK BANK",
                    "CANARA BANK",
                    "UNION BANK",
                    "BANK OF BARODA",
                    "PNB BANK",
                    "IDBI BANK",
                    "FEDERAL BANK",
                    "INDUSIND BANK",
                ]
            )
            or p_upper.endswith("BANK")
            or "BANK A/C" in p_upper
        )
        if is_real_bank:
            if is_payment:
                if any(
                    k in text for k in ["EMI", "LOAN", "REPAY", "OD", "OVERDRAFT"]
                ):
                    return "Secured Loans"
                return "Bank Accounts"
            else:
                if any(
                    k in text or k in p_upper
                    for k in [
                        "INTEREST",
                        "INTREST",
                        "INT CR",
                        "CREDIT INT",
                        "INT ",
                        "INT/",
                        "INT-",
                        "INT.",
                        "BANK INT",
                    ]
                ):
                    return "Indirect Income"
                if is_large_amt and is_round_amt:
                    return "Secured Loans"
                return "Bank Accounts"

    # ── STEP 7: E-COMMERCE & FOOD DELIVERY ───────────────────────────────
    ECOM_KWS = [
        "AMAZON",
        "FLIPKART",
        "MYNTRA",
        "AJIO",
        "NYKAA",
        "MEESHO",
        "SNAPDEAL",
        "JIO MART",
        "JIOMART",
        "BIGBASKET",
        "MILKBASKET",
        "BLINKIT",
        "ZEPTO",
        "SWIGGY",
        "ZOMATO",
        "INSTAMART",
        "DUNZO",
        "URBAN COMPANY",
        "URBANCLAP",
    ]
    if any(k in text for k in ECOM_KWS):
        if is_payment:
            return (
                "Indirect Expenses"
                if is_small_amt or is_medium_amt
                else "Purchase Accounts"
            )
        else:
            return "Sundry Debtors"

    # ── STEP 8a: DIRECT EXPENSES ─────────────────────────────────────────
    DIRECT_EXPENSE_KWS = [
        "FREIGHT",
        "BHADA",
        "CARRIAGE",
        "CARTAGE",
        "LOADING",
        "UNLOADING",
        "HAMALI",
        "COOLIE",
        "OCTROI",
        "GATE PASS",
        "CUSTOMS",
        "LABOUR",
        "WAGES",
        "RAW MATERIAL",
        "TPT",
        "TRANSPORT",
        "TRANSPORTATION",
    ]
    if any(k in text for k in DIRECT_EXPENSE_KWS):
        return "Direct Expenses" if is_payment else "Direct Income"

    # ── STEP 8b: UTILITY & BILLS ──────────────────────────────────────────
    UTILITY_KWS = [
        "ELECTRICITY",
        "BIJLI",
        "POWER",
        "TELEPHONE",
        "MOBILE",
        "RECHARGE",
        "WIFI",
        "BROADBAND",
        "AIRTEL",
        "JIO",
        "VODAFONE",
        "BSNL",
        "TATA SKY",
        "PETROL",
        "FUEL",
        "DIESEL",
        "INDANE",
        "HPCL",
        "BPCL",
        "IOCL",
        "RENT",
        "LEASE",
        "MAINTENANCE",
        "PARKING",
        "PARKING CHG",
        "PARKING CHARGES",
        "PARKING EXPENSE",
        "PARKING FEE",
        "TOLL",
        "TOLL TAX",
        "FASTAG",
        "NETC FASTAG",
        "WATER BILL",
        "GAS BILL",
        "GOOGLE PLAY",
        "NETFLIX",
        "AMAZON PRIME",
        "HOTSTAR",
        "SPOTIFY",
        "INSTAALERT",
        "ALERTCHG",
        "SMS CHARGE",
        "SOUND BOX",
        "EDC RENTAL",
        "POS RENTAL",
        "MSEB",
        "BEST",
        "TATA POWER",
        "ADANI ELECTRICITY",
        "TORRENT POWER",
        "MAHADISCOM",
    ]
    if any(k in text for k in UTILITY_KWS):
        return "Indirect Expenses" if is_payment else "Indirect Income"

    # ── STEP 8c: HEALTHCARE & TRADE VENDORS ──────────────────────────────
    TRADE_HEALTH_KWS = [
        "DIABETIC",
        "FOOTWEAR",
        "SHOES",
        "DIAGNOSTICS",
        "HEALTHCARE",
        "HOSPITAL",
        "CLINIC",
        "LAB ",
        "PHARMA",
        "MEDICAL",
    ]
    if any(k in text for k in TRADE_HEALTH_KWS):
        return "Sundry Debtors" if is_receipt else "Sundry Creditors"

    # ── STEP 9: PAYMENT WALLETS ──────────────────────────────────────────
    WALLET_KWS = ["GOOGLE PAY", "GPAY", "PAYTM", "PHONEPE", "BHIM", "FAMPAY"]
    if any(k in text for k in WALLET_KWS):
        if is_payment:
            return (
                "Indirect Expenses" if is_small_amt else "Loans & Advances (Asset)"
            )
        else:
            return (
                "Sundry Debtors"
                if is_medium_amt or is_large_amt
                else "Indirect Income"
            )

    # Note: Duplicate STATUTORY_TAX (old Step 10) & BANK_CHARGE (old Step 11) checks removed (Issues #6 & #7)

    # ── STEP 12: SALARY & PAYROLL ────────────────────────────────────────
    if any(
        k in text
        for k in [
            "SALARY",
            "SALARIES",
            "WAGES",
            "STIPEND",
            "BONUS",
            "PAYROLL",
            "COMPENSATION",
            "HR PAY",
        ]
    ):
        if is_payment:
            return "Indirect Expenses"
        else:
            return "Indirect Income"

    # ── STEP 13: GENERAL EXPENSE KEYWORDS ───────────────────────────────
    EXPENSE_KWS = [
        "EXPENSE",
        "EXPENSES",
        "PF ",
        "ESI",
        "AUDIT",
        "LEGAL",
        "FEE",
        "FEES",
        "COMMISSION",
        "PRINTING",
        "STATIONERY",
        "COURIER",
        "POSTAGE",
        "CLEANING",
        "REPAIR",
        "REPAIRS",
        "SOFTWARE",
        "DOMAIN",
        "HOSTING",
        "CLOUD",
        "TAXI",
        "CAB",
        "TRAVEL",
        "CONVEYANCE",
        "SUBSCRIPTION",
        "DONATION",
        "WELFARE",
        "INSURANCE",
        "PREMIUM",
    ]
    if any(k in text for k in EXPENSE_KWS):
        return "Indirect Expenses" if is_payment else "Indirect Income"

    # ── STEP 14: PERSONAL / DRAWINGS ────────────────────────────────────
    if any(
        k in text
        for k in [
            "LIC",
            "MEDICLAIM",
            "MEDICINE",
            "HEALTH INSURANCE",
            "PERSONAL EXP",
        ]
    ):
        return "Capital Account / Drawings" if is_payment else "Indirect Income"

    # ── STEP 15: HUMAN PERSONS — Loans between individuals ──────────────
    is_human = any(
        t in text
        for t in [
            "BHAI",
            "KUMAR",
            "LAL",
            "DEVI",
            "SHAH",
            "PATEL",
            "MEHTA",
            "MANDALIA",
            "BEN ",
            "KAKA ",
        ]
    )
    is_company = any(
        b in text
        for b in [
            "LTD",
            "LIMITED",
            "PVT",
            "PRIVATE",
            "CORP",
            "CORPORATION",
            "TRADERS",
            "TRADER",
            "ENTERPRISE",
            "ENTERPRISES",
            "INDUSTRIES",
            "INDUSTRY",
            "INC",
            "LLC",
            "DISTRIBUTOR",
            "DISTRIBUTORS",
            "PRODUCTS",
            "PRODUCT",
            "AGENCIES",
            "AGENCY",
            "SUPPLIERS",
            "SUPPLIER",
            "MART",
            "MANUFACTURING",
            "PHARMA",
            "MILLS",
            "SOLUTIONS",
            "TECHNOLOGIES",
            "SERVICES",
            "INFRA",
            "EXPORTS",
            "IMPORTS",
            "HARDWARE",
            "MOTORS",
            "AUTO",
            "STEEL",
            "CHEMICALS",
            "TEXTILES",
            "TRADING",
            "COMMERCE",
            "LOGISTICS",
        ]
    )
    if is_human and not is_company:
        has_expense_descriptor = any(
            kw in text
            for kw in [
                "PARKING",
                "RENT",
                "TPT",
                "TRANSPORT",
                "FREIGHT",
                "SALARY",
                "PETROL",
                "DIESEL",
                "FUEL",
                "ELECTRICITY",
                "POWER",
                "TEA",
                "FOOD",
                "SNACKS",
                "REPAIR",
                "MAINTENANCE",
                "STATIONERY",
                "POSTAGE",
                "COURIER",
                "TOLL",
                "FASTAG",
                "LOADING",
                "UNLOADING",
                "HAMALI",
                "CARTAGE",
                "BHADA",
                "ALLOWANCE",
                "REIMBURSEMENT",
                "CHARGE",
                "CHARGES",
                "EXPENSE",
                "EXPENSES",
                "EXP",
            ]
        )
        if not has_expense_descriptor:
            res_group = "Loans & Advances (Asset)" if is_payment else "Unsecured Loans"
        else:
            res_group = "Indirect Expenses" if is_payment else "Indirect Income"
    elif (
        is_company
        and party_name
        and party_name.upper().strip() not in ("BANK CHARGES", "CASH")
    ):
        res_group = "Sundry Creditors" if is_payment else "Sundry Debtors"
    else:
        res_group = "Sundry Creditors" if is_payment else "Sundry Debtors"

    # ── DOUBLE-ENTRY ACCOUNTING NATURE GUARD ────────────────────────────────
    has_reversal_kw = any(
        rk in text
        for rk in [
            "REFUND",
            "REVERSAL",
            "CASHBACK",
            "REIMBURSEMENT",
            "CLAIM",
            "DISCOUNT",
            "CREDIT NOTE",
            "CN ",
        ]
    )
    if (
        is_receipt
        and res_group
        in ("Indirect Expenses", "Direct Expenses", "Purchase Accounts", "Sundry Creditors")
        and not has_reversal_kw
    ):
        p_clean = (party_name or "").upper().strip()
        if p_clean and p_clean not in (
            "BANK CHARGES",
            "CASH",
            "CASH ACCOUNT",
            "UNKNOWN",
        ):
            return "Sundry Debtors"
        return "Indirect Income"

    has_dn_kw = any(
        rk in text for rk in ["DEBIT NOTE", "DN ", "CHARGEBACK"]
    )
    if (
        is_payment
        and res_group
        in ("Sales Accounts", "Direct Income", "Indirect Income", "Sundry Debtors")
        and not has_dn_kw
    ):
        p_clean = (party_name or "").upper().strip()
        if p_clean and p_clean not in (
            "BANK CHARGES",
            "CASH",
            "CASH ACCOUNT",
            "UNKNOWN",
        ):
            return "Sundry Creditors"
        return "Indirect Expenses"

    return res_group
