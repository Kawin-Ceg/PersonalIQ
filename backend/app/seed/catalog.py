"""Demo catalog. Curated, labelled demo data: not live merchant inventory.

Each product has a `need` so the agents can compare alternatives for the same job
(three mattresses, three sofas, ...). Scores are 0-100. Prices are strings so they
load straight into Decimal.
"""

MERCHANTS = [
    {"slug": "harbor-pine", "name": "Harbor & Pine Home", "shipping_flat": "49.00", "free_shipping_over": "999.00", "return_window_days": 30},
    {"slug": "kettlewell", "name": "Kettlewell Kitchen", "shipping_flat": "9.95", "free_shipping_over": "99.00", "return_window_days": 60},
    {"slug": "volt-corner", "name": "Volt Corner Electronics", "shipping_flat": "14.99", "free_shipping_over": "250.00", "return_window_days": 15},
    {"slug": "brightside", "name": "Brightside Supply", "shipping_flat": "7.50", "free_shipping_over": "75.00", "return_window_days": 30},
]

# (sku, merchant, category, need, name, price, quality, durability, rating, reviews, warranty_months, materials, description)
_P = [
    # Furniture
    ("FUR-001", "harbor-pine", "Furniture", "mattress", "Queen Hybrid Mattress, Medium Firm", "449.00", 86, 84, 4.6, 2140, 120, ["foam", "steel coil"], "Pocket coils under a foam comfort layer. Suits most sleepers."),
    ("FUR-002", "harbor-pine", "Furniture", "mattress", "Queen Memory Foam Mattress", "329.00", 78, 72, 4.4, 3810, 60, ["foam"], "All-foam, soft feel. Ships compressed in a box."),
    ("FUR-003", "harbor-pine", "Furniture", "mattress", "Queen Latex Mattress, Firm", "689.00", 92, 93, 4.7, 640, 180, ["latex", "wool"], "Natural latex with a wool cover. Long lifespan, firm support."),
    ("FUR-004", "harbor-pine", "Furniture", "bed_frame", "Steel Platform Bed Frame, Queen", "159.00", 74, 88, 4.5, 5120, 60, ["steel"], "No box spring needed. Tool-free assembly."),
    ("FUR-005", "harbor-pine", "Furniture", "bed_frame", "Solid Oak Bed Frame, Queen", "389.00", 90, 94, 4.7, 410, 120, ["oak"], "Solid hardwood with slatted base."),
    ("FUR-006", "harbor-pine", "Furniture", "bed_frame", "Upholstered Bed Frame, Leather Headboard", "279.00", 80, 70, 4.3, 980, 24, ["leather", "pine"], "Padded faux-panel headboard in genuine leather."),
    ("FUR-007", "harbor-pine", "Furniture", "sofa", "Three-Seat Fabric Sofa", "549.00", 82, 78, 4.4, 1320, 36, ["polyester", "hardwood"], "Deep seats, removable cushion covers."),
    ("FUR-008", "harbor-pine", "Furniture", "sofa", "Compact Loveseat, Performance Fabric", "389.00", 79, 82, 4.5, 860, 36, ["performance fabric", "hardwood"], "Stain-resistant fabric. Fits small living rooms."),
    ("FUR-009", "harbor-pine", "Furniture", "sofa", "Leather Sofa, Cognac", "899.00", 88, 90, 4.6, 520, 60, ["leather", "hardwood"], "Top-grain leather on a kiln-dried frame."),
    ("FUR-010", "harbor-pine", "Furniture", "dining", "Four-Seat Dining Set, Rubberwood", "299.00", 76, 80, 4.3, 740, 12, ["rubberwood"], "Table and four chairs."),
    ("FUR-011", "harbor-pine", "Furniture", "dining", "Drop-Leaf Dining Table", "179.00", 72, 74, 4.2, 690, 12, ["pine"], "Folds to 12 inches deep. Chairs not included."),
    ("FUR-012", "harbor-pine", "Furniture", "desk", "Writing Desk, Walnut Veneer", "189.00", 78, 76, 4.4, 1100, 24, ["walnut veneer", "steel"], "47-inch top with one drawer."),
    ("FUR-013", "harbor-pine", "Furniture", "desk", "Height-Adjustable Standing Desk", "349.00", 86, 84, 4.6, 2470, 60, ["steel", "laminate"], "Dual motor, 4 memory presets."),
    ("FUR-014", "harbor-pine", "Furniture", "office_chair", "Ergonomic Office Chair, Mesh Back", "149.99", 84, 86, 4.5, 6230, 36, ["mesh", "nylon"], "Adjustable arms and seat depth."),
    ("FUR-015", "harbor-pine", "Furniture", "office_chair", "Task Chair, Bonded Leather", "119.00", 66, 58, 3.9, 1840, 12, ["bonded leather"], "Padded seat. Bonded leather can peel over time."),
    ("FUR-016", "harbor-pine", "Furniture", "office_chair", "Ergonomic Chair with Lumbar Support", "239.00", 90, 88, 4.7, 1530, 60, ["mesh", "aluminium"], "Adjustable lumbar, 4D arms, recline lock."),
    ("FUR-017", "harbor-pine", "Furniture", "storage", "Five-Shelf Bookcase", "89.00", 70, 72, 4.3, 3020, 12, ["engineered wood"], "Five fixed shelves, wall anchor included."),
    # Kitchen
    ("KIT-001", "kettlewell", "Kitchen", "cookware", "10-Piece Stainless Cookware Set", "189.00", 88, 94, 4.7, 4410, 240, ["stainless steel"], "Tri-ply, oven safe, induction ready."),
    ("KIT-002", "kettlewell", "Kitchen", "cookware", "8-Piece Nonstick Cookware Set", "89.00", 72, 58, 4.3, 7020, 12, ["aluminium", "nonstick coating"], "Light and easy to clean. Coating wears in 2-3 years."),
    ("KIT-003", "kettlewell", "Kitchen", "microwave", "Countertop Microwave, 1.1 cu ft", "119.00", 78, 76, 4.4, 5310, 12, ["steel"], "1000 W with sensor cooking."),
    ("KIT-004", "kettlewell", "Kitchen", "kettle", "Electric Kettle, 1.7 L", "39.99", 80, 78, 4.6, 8840, 24, ["stainless steel"], "Auto shut-off, boils in about 4 minutes."),
    ("KIT-005", "kettlewell", "Kitchen", "coffee", "Drip Coffee Maker, 12 Cup", "59.00", 74, 70, 4.3, 4120, 12, ["plastic", "glass"], "Programmable with a warming plate."),
    ("KIT-006", "kettlewell", "Kitchen", "knives", "Chef Knife Set with Block, 8 Piece", "99.00", 84, 86, 4.6, 2960, 120, ["stainless steel", "acacia"], "Forged blades, includes honing steel."),
    ("KIT-007", "kettlewell", "Kitchen", "dinnerware", "Stoneware Dinnerware Set, Service for 4", "69.00", 78, 74, 4.5, 2210, 12, ["stoneware"], "Plates, bowls and mugs. Dishwasher safe."),
    ("KIT-008", "kettlewell", "Kitchen", "blender", "Personal Blender", "49.00", 72, 68, 4.2, 6630, 12, ["plastic"], "Two travel cups included."),
    ("KIT-009", "kettlewell", "Kitchen", "toaster", "Two-Slice Toaster", "34.99", 70, 70, 4.3, 3870, 12, ["steel"], "Wide slots, bagel setting."),
    # Electronics
    ("ELE-001", "volt-corner", "Electronics", "tv", "43-inch 4K Smart TV", "279.00", 80, 78, 4.5, 3390, 12, [], "HDR, built-in streaming apps."),
    ("ELE-002", "volt-corner", "Electronics", "tv", "55-inch 4K Smart TV", "429.00", 84, 80, 4.6, 2780, 12, [], "HDR, 120 Hz motion, voice remote."),
    ("ELE-003", "volt-corner", "Electronics", "router", "Wi-Fi 6 Router", "99.00", 84, 82, 4.5, 2050, 24, [], "Covers about 2,000 sq ft."),
    ("ELE-004", "volt-corner", "Electronics", "lighting", "LED Floor Lamp, Dimmable", "59.00", 76, 78, 4.4, 1890, 24, ["steel"], "Warm to cool white, remote included."),
    ("ELE-005", "volt-corner", "Electronics", "power", "Surge Protector, 12 Outlets", "29.99", 82, 86, 4.7, 9120, 60, [], "4,320 joules, 6 ft cord."),
    # Cleaning
    ("CLN-001", "brightside", "Cleaning", "vacuum", "Cordless Stick Vacuum", "199.00", 82, 74, 4.4, 4480, 24, [], "40 minute runtime, wall dock."),
    ("CLN-002", "brightside", "Cleaning", "vacuum", "Bagless Upright Vacuum", "139.00", 78, 82, 4.4, 3150, 60, [], "Corded, strong on carpet."),
    ("CLN-003", "brightside", "Cleaning", "mop", "Spin Mop and Bucket Set", "34.99", 76, 70, 4.4, 7710, 12, ["microfiber"], "Two refill heads included."),
    ("CLN-004", "brightside", "Cleaning", "supplies", "Cleaning Starter Kit, 12 Items", "44.99", 72, 60, 4.3, 1270, 0, [], "Sprays, cloths, sponges and gloves."),
    ("CLN-005", "brightside", "Cleaning", "trash", "Step Trash Can, 13 Gallon", "49.00", 80, 86, 4.6, 5530, 60, ["stainless steel"], "Soft-close lid, removable liner."),
    # Household
    ("HOU-001", "brightside", "Household", "sheets", "Cotton Percale Sheet Set, Queen", "79.00", 84, 80, 4.6, 6420, 12, ["cotton"], "Crisp, breathable weave."),
    ("HOU-002", "brightside", "Household", "comforter", "Down-Alternative Comforter, Queen", "69.00", 78, 74, 4.5, 8030, 12, ["polyester"], "All-season weight, machine washable."),
    ("HOU-003", "brightside", "Household", "pillows", "Pillow Pair, Medium Support", "45.00", 76, 70, 4.3, 5210, 12, ["polyester"], "Two pillows, shredded fill."),
    ("HOU-004", "brightside", "Household", "towels", "Bath Towel Set, 6 Piece", "49.00", 82, 78, 4.6, 4370, 12, ["cotton"], "Two each of bath, hand and wash towels."),
    ("HOU-005", "brightside", "Household", "curtains", "Blackout Curtains, 2 Panels", "39.00", 76, 76, 4.4, 6960, 12, ["polyester"], "52 x 84 inches each."),
    ("HOU-006", "brightside", "Household", "tools", "Household Tool Kit, 65 Piece", "39.99", 74, 80, 4.5, 3310, 12, ["steel"], "Hammer, screwdrivers, tape and more."),
    ("HOU-007", "brightside", "Household", "hangers", "Velvet Hangers, 50 Pack", "24.99", 72, 70, 4.5, 11240, 0, ["velvet", "plastic"], "Slim, non-slip."),
    ("HOU-008", "brightside", "Household", "first_aid", "First Aid Kit, 140 Piece", "24.99", 80, 80, 4.7, 4890, 0, [], "Covers common minor injuries."),
]

PRODUCTS = [
    {
        "sku": sku,
        "merchant": merchant,
        "category": category,
        "name": name,
        "price": price,
        "quality_score": q,
        "durability_score": d,
        "rating": rating,
        "review_count": reviews,
        "warranty_months": warranty,
        "description": desc,
        "attributes": {"need": need, "materials": materials},
    }
    for (sku, merchant, category, need, name, price, q, d, rating, reviews, warranty, materials, desc) in _P
]

# Priya has history (onboarded, 90 days of spending, two reviews). Theo is new, to demo onboarding.
# Each user has a home currency; budgets and spending are in it. The catalog stays in USD and is
# converted for display with fixed demo rates (app/services/fx.py).
USERS = [
    {
        "email": "priya@demo.personaliq.app",
        "name": "Priya Raman",
        "timezone": "Asia/Kolkata",
        "currency": "INR",
        "budgets": [
            {"name": "Apartment move", "period": "one_off", "limit_amount": "169000.00"},
            {"name": "Monthly discretionary", "period": "monthly", "limit_amount": "85000.00"},
        ],
        "onboarding": {
            "priorities": ["durability", "quality"],
            "price_sensitivity": "medium",
            "avoid_materials": ["leather"],
            "like_merchants": ["kettlewell"],
            "avoid_merchants": [],
            "likes": ["Minimal, neutral colours"],
            "dislikes": ["Assembly that needs two people"],
            "monthly_budget": "85000.00",
        },
        # (days ago, merchant, category, amount in INR)
        "transactions": [
            (3, "FreshCart", "Groceries", "7300.00"), (6, "Metro Transit", "Transport", "3800.00"),
            (9, "Kettlewell Kitchen", "Home", "3379.00"), (12, "FreshCart", "Groceries", "7790.00"),
            (15, "Streamly", "Subscriptions", "649.00"), (19, "Corner Bistro", "Dining", "3250.00"),
            (24, "FreshCart", "Groceries", "6575.00"), (28, "Harbor & Pine Home", "Home", "15970.00"),
            (33, "Metro Transit", "Transport", "3800.00"), (37, "Corner Bistro", "Dining", "4410.00"),
            (41, "FreshCart", "Groceries", "6850.00"), (45, "Streamly", "Subscriptions", "649.00"),
            (52, "Brightside Supply", "Home", "5450.00"), (58, "FreshCart", "Groceries", "7485.00"),
            (63, "Metro Transit", "Transport", "3800.00"), (67, "Volt Corner Electronics", "Electronics", "8365.00"),
            (71, "Corner Bistro", "Dining", "3530.00"), (75, "Streamly", "Subscriptions", "649.00"),
            (80, "FreshCart", "Groceries", "6700.00"), (86, "Kettlewell Kitchen", "Home", "5830.00"),
        ],
        "feedback": [
            {"sku": "KIT-002", "rating": 4, "didnt_work": "coating peeled within a year", "reasons": ["durability"]},
            {"sku": "KIT-004", "rating": 9, "worked": "fast, still like new after two years", "reasons": ["quality"]},
        ],
    },
    {
        "email": "theo@demo.personaliq.app",
        "name": "Theo Lindqvist",
        "timezone": "Europe/Stockholm",
        "currency": "SEK",
        "budgets": [{"name": "Monthly discretionary", "period": "monthly", "limit_amount": "6400.00"}],
    },
]
