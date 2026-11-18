"""Lesson 1 - MongoDB Document Store: shop orders.
Chay: docker compose up -d  (mongo:8 port 27017)
      pip install pymongo pandas
      python shop_mongo.py
"""
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client.shop
orders = db.orders

def seed():
    orders.delete_many({})
    orders.insert_many([
        {"_id": 1001, "customer": {"name": "Linh", "city": "Hanoi"}, "status": "paid",
         "items": [{"sku": "BK-01", "title": "Python Basics", "qty": 2, "price": 12.5},
                   {"sku": "BK-07", "title": "SQL in Practice", "qty": 1, "price": 18.0}],
         "tags": ["student", "first-order"]},
        {"_id": 1002, "customer": {"name": "Nam", "city": "Da Nang"}, "status": "shipped",
         "items": [{"sku": "BK-03", "title": "Data Viz", "qty": 1, "price": 22.0}]},
        {"_id": 1003, "customer": {"name": "Mai", "city": "Hanoi"}, "status": "paid",
         "items": [{"sku": "BK-01", "title": "Python Basics", "qty": 1, "price": 12.5}],
         "coupon": "WELCOME10"},
        {"_id": 1004, "customer": {"name": "Hung", "city": "Hue"}, "status": "paid",
         "items": [{"sku": "BK-07", "title": "SQL in Practice", "qty": 3, "price": 18.0}]},
        {"_id": 1005, "customer": {"name": "An", "city": "Hanoi"}, "status": "cancelled",
         "items": [{"sku": "BK-03", "title": "Data Viz", "qty": 2, "price": 22.0}]},
    ])
    print("seeded:", orders.count_documents({}))

def ex_find_by_sku(sku="BK-01"):
    print(f"\n-- orders containing {sku} --")
    for d in orders.find({"items.sku": sku}, {"_id": 1, "customer.name": 1, "status": 1}):
        print(d)

def ex_revenue_per_city():
    print("\n-- revenue per city --")
    pipe = [
        {"$match": {"status": {"$in": ["paid", "shipped"]}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$customer.city",
                    "units": {"$sum": "$items.qty"},
                    "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}}}},
        {"$sort": {"revenue": -1}},
    ]
    for d in orders.aggregate(pipe):
        print(d)

def ex_update_delete():
    orders.update_one({"_id": 1001}, {"$set": {"status": "shipped"}})
    orders.update_many({"status": "paid"}, {"$set": {"reviewed": False}})
    orders.update_one({"_id": 1002}, {"$push": {"tags": "gift"}})
    print("\nupdate OK")
    print("order 1001:", orders.find_one({"_id": 1001}, {"status": 1}))

def ex_index():
    print("\n-- explain truoc index --")
    print(orders.find({"customer.city": "Hanoi", "status": "paid"}).explain()["queryPlanner"]["winningPlan"]["stage"])
    orders.create_index([("customer.city", 1), ("status", 1)])
    print("-- explain sau index --")
    print(orders.find({"customer.city": "Hanoi", "status": "paid"}).explain()["queryPlanner"]["winningPlan"]["stage"])

if __name__ == "__main__":
    seed()
    ex_find_by_sku("BK-01")
    ex_revenue_per_city()
    ex_update_delete()
    ex_index()
