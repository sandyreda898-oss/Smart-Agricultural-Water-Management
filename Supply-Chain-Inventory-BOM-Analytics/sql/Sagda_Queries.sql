/* =========================================================
QUERY 1: INVENTORY & BOM KPIs
========================================================= */

SELECT
COUNT(DISTINCT ProductID) AS Total_Products,
COUNT(DISTINCT ComponentID) AS Total_Components,
SUM([Required Qty]) AS Total_Required_Quantity,
SUM([Component Capacity]) AS Total_Recorded_Capacity,
SUM(
CASE
WHEN [Required Qty] > [Component Capacity]
THEN 1 ELSE 0
END
) AS Potential_Shortage_Rows
FROM dbo.BOM;

/* =========================================================
QUERY 2: COMPONENT SHORTAGE & CAPACITY COVERAGE
========================================================= */

WITH ComponentRequirements AS
(
SELECT
ComponentID,
SUM([Required Qty]) AS Total_Required_Qty,
MAX([Component Capacity]) AS Component_Capacity
FROM dbo.BOM
GROUP BY ComponentID
)
SELECT
ComponentID,
Total_Required_Qty,
Component_Capacity,
Total_Required_Qty - Component_Capacity AS Capacity_Gap,
CAST(
Component_Capacity * 100.0 /
NULLIF(Total_Required_Qty, 0)
AS DECIMAL(10,2)
) AS Capacity_Coverage_Percentage,
CASE
WHEN Total_Required_Qty > Component_Capacity
THEN 'Potential Capacity Shortage'
ELSE 'Capacity Sufficient'
END AS Capacity_Status
FROM ComponentRequirements
ORDER BY Capacity_Gap DESC;

/* =========================================================
QUERY 3: PRODUCTS WITH HIGHEST DEMAND
========================================================= */

SELECT TOP 20
ProductID,
MAX([Product Demand]) AS Product_Demand,
SUM([Required Qty]) AS Total_Required_Quantity,
COUNT(DISTINCT ComponentID) AS Required_Components
FROM dbo.BOM
GROUP BY ProductID
ORDER BY Product_Demand DESC;

/* =========================================================
QUERY 4: PRODUCT-LEVEL COMPONENT REQUIREMENTS
========================================================= */

SELECT
ProductID,
ComponentID,
[Qty Per Unit],
[Product Demand],
[Required Qty],
[Component Capacity],
CAST(
[Qty Per Unit] * [Product Demand]
AS DECIMAL(18,2)
) AS Recalculated_Required_Qty,
CASE
WHEN [Qty Per Unit] * [Product Demand] <> [Required Qty]
THEN 'Check Required Quantity'
ELSE 'Calculation Matches'
END AS Calculation_Check
FROM dbo.BOM
ORDER BY ProductID, ComponentID;

/* =========================================================
QUERY 5: BOM DATA QUALITY CHECK
========================================================= */

SELECT
COUNT(*) AS Total_Rows,

SUM(CASE WHEN ProductID IS NULL THEN 1 ELSE 0 END)
    AS Missing_Product_ID,

SUM(CASE WHEN ComponentID IS NULL THEN 1 ELSE 0 END)
    AS Missing_Component_ID,

SUM(CASE WHEN [Qty Per Unit] IS NULL THEN 1 ELSE 0 END)
    AS Missing_Qty_Per_Unit,

SUM(CASE WHEN [Product Demand] IS NULL THEN 1 ELSE 0 END)
    AS Missing_Product_Demand,

SUM(CASE WHEN [Required Qty] IS NULL THEN 1 ELSE 0 END)
    AS Missing_Required_Qty,

SUM(CASE WHEN [Component Capacity] IS NULL THEN 1 ELSE 0 END)
    AS Missing_Component_Capacity,

SUM(
    CASE
        WHEN [Required Qty] IS NOT NULL
         AND [Qty Per Unit] IS NOT NULL
         AND [Product Demand] IS NOT NULL
         AND [Required Qty] <>
             [Qty Per Unit] * [Product Demand]
        THEN 1 ELSE 0
    END
) AS Calculation_Mismatch_Rows

FROM dbo.BOM;


/* =========================================================
QUERY 6: OVERALL BUSINESS KPIs
========================================================= */

SELECT
COUNT(DISTINCT order_id) AS Total_Orders,
COUNT(DISTINCT customer_id) AS Total_Customers,
COUNT(DISTINCT product_card_id) AS Total_Products,
SUM(order_item_quantity) AS Total_Quantity_Sold,
SUM(sales) AS Gross_Sales,
SUM(order_item_discount) AS Total_Discount,
SUM(order_item_total) AS Net_Sales,
SUM(order_profit_per_order) AS Total_Profit,
CAST(
SUM(order_profit_per_order) * 100.0 /
NULLIF(SUM(sales), 0)
AS DECIMAL(10,2)
) AS Profit_Margin_Percentage
FROM DataCo_Cleaned;

/* =========================================================
QUERY 7: MONTHLY PRODUCT DEMAND
========================================================= */

SELECT
product_name,
YEAR(TRY_CONVERT(date, order_date_dateorders)) AS Order_Year,
MONTH(TRY_CONVERT(date, order_date_dateorders)) AS Order_Month,
SUM(order_item_quantity) AS Quantity_Sold,
COUNT(DISTINCT order_id) AS Total_Orders
FROM DataCo_Cleaned
GROUP BY
product_name,
YEAR(TRY_CONVERT(date, order_date_dateorders)),
MONTH(TRY_CONVERT(date, order_date_dateorders))
ORDER BY
product_name,
Order_Year,
Order_Month;

/* =========================================================
QUERY 8: DELIVERY PERFORMANCE BY SHIPPING MODE
========================================================= */

SELECT
shipping_mode,
COUNT(DISTINCT order_id) AS Total_Orders,

AVG(
    CAST(days_for_shipping_real AS DECIMAL(10,2))
) AS Avg_Actual_Shipping_Days,

AVG(
    CAST(days_for_shipment_scheduled AS DECIMAL(10,2))
) AS Avg_Scheduled_Shipping_Days,

AVG(
    CAST(days_for_shipping_real AS DECIMAL(10,2))
) -
AVG(
    CAST(days_for_shipment_scheduled AS DECIMAL(10,2))
) AS Avg_Delay_Days,

CAST(
    AVG(CAST(late_delivery_risk AS DECIMAL(10,2))) * 100
    AS DECIMAL(10,2)
) AS Late_Risk_Percentage

FROM DataCo_Cleaned
GROUP BY shipping_mode
ORDER BY Avg_Delay_Days DESC;

/* =========================================================
QUERY 9: HIGH DEMAND AND LOW PROFIT
========================================================= */

SELECT
product_name,
SUM(order_item_quantity) AS Quantity_Sold,
SUM(sales) AS Total_Sales,
SUM(order_profit_per_order) AS Total_Profit,

CAST(
    SUM(order_profit_per_order) * 100.0 /
    NULLIF(SUM(sales), 0)
    AS DECIMAL(10,2)
) AS Profit_Margin_Percentage

FROM DataCo_Cleaned
GROUP BY product_name
HAVING SUM(order_item_quantity) > 0
ORDER BY
Profit_Margin_Percentage ASC,
Quantity_Sold DESC;

/* =========================================================
QUERY 10: PRODUCT DEMAND PRESSURE
========================================================= */

SELECT
product_name,
SUM(order_item_quantity) AS Total_Quantity_Sold,
COUNT(DISTINCT order_id) AS Total_Orders,

COUNT(DISTINCT
    CONVERT(
        CHAR(7),
        TRY_CONVERT(date, order_date_dateorders),
        120
    )
) AS Active_Months,

CAST(
    SUM(order_item_quantity) * 1.0 /
    NULLIF(
        COUNT(DISTINCT
            CONVERT(
                CHAR(7),
                TRY_CONVERT(date, order_date_dateorders),
                120
            )
        ),
        0
    )
    AS DECIMAL(10,2)
) AS Avg_Monthly_Demand

FROM DataCo_Cleaned
GROUP BY product_name
ORDER BY Avg_Monthly_Demand DESC;

/* =========================================================
QUERY 11: TOTAL COMPONENT COST & FINANCIAL EXPOSURE
========================================================= */

WITH ComponentTotalReq AS (
    SELECT
        ComponentID,
        SUM([Required Qty]) AS Total_Required_Qty
    FROM dbo.BOM
    GROUP BY ComponentID
)
SELECT 
    c.ComponentID,
    c.ComponentName,
    c.AvailableQty,
    ctr.Total_Required_Qty,
    c.UnitCost,
    CAST(ctr.Total_Required_Qty * c.UnitCost AS DECIMAL(18,2)) AS Total_Cost_Required,
    CASE 
        WHEN ctr.Total_Required_Qty > c.AvailableQty THEN 'Shortage Risk'
        else 'Sufficient'
    END AS Stock_Status
FROM dbo.Components c
LEFT JOIN ComponentTotalReq ctr ON c.ComponentID = ctr.ComponentID
ORDER BY Total_Cost_Required DESC;

/* =========================================================
QUERY 12: COMPONENT INVENTORY GAP & DEFICIT COST
========================================================= */

WITH AggregatedBOM AS (
    SELECT
        ComponentID,
        SUM([Required Qty]) AS Total_Required_Qty
    FROM dbo.BOM
    GROUP BY ComponentID
)
SELECT 
    c.ComponentID,
    c.ComponentName,
    c.AvailableQty,
    ab.Total_Required_Qty,
    CASE 
        WHEN ab.Total_Required_Qty > c.AvailableQty 
        THEN ab.Total_Required_Qty - c.AvailableQty 
        ELSE 0 
    END AS Deficit_Quantity,
    c.UnitCost,
    CASE 
        WHEN ab.Total_Required_Qty > c.AvailableQty 
        THEN CAST((ab.Total_Required_Qty - c.AvailableQty) * c.UnitCost AS DECIMAL(18,2))
        ELSE 0.00 
    END AS Deficit_Financial_Cost
FROM dbo.Components c
JOIN AggregatedBOM ab ON c.ComponentID = ab.ComponentID
WHERE ab.Total_Required_Qty > c.AvailableQty
ORDER BY Deficit_Financial_Cost DESC;



/* =========================================================
   1) OVERALL BUSINESS KPIs
   السؤال:
   - الشركة باعت كام؟
   - حققت كام Profit؟
   - عدد الطلبات والعملاء والمنتجات؟
   - إجمالي الكمية والخصومات؟
   ========================================================= */

SELECT
    COUNT(DISTINCT order_id) AS Total_Orders,
    COUNT(DISTINCT customer_id) AS Total_Customers,
    COUNT(DISTINCT product_card_id) AS Total_Products,
    SUM(order_item_quantity) AS Total_Quantity,
    SUM(sales) AS Gross_Sales,
    SUM(order_item_discount) AS Total_Discount,
    SUM(order_item_total) AS Net_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    CAST(
        SUM(order_profit_per_order) * 100.0 / NULLIF(SUM(sales), 0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin_Percentage
FROM DataCo_Cleaned;


/* =========================================================
   2) MONTHLY SALES & PROFIT TREND
   السؤال:
   - المبيعات والأرباح بتزيد ولا بتقل مع الوقت؟
   - أنهي شهر كان الأقوى؟
   ========================================================= */

SELECT
    YEAR(TRY_CONVERT(date, order_date_dateorders)) AS Order_Year,
    MONTH(TRY_CONVERT(date, order_date_dateorders)) AS Order_Month,
    SUM(sales) AS Total_Sales,
    SUM(order_item_total) AS Net_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    COUNT(DISTINCT order_id) AS Total_Orders,
    SUM(order_item_quantity) AS Total_Quantity
FROM DataCo_Cleaned
GROUP BY
    YEAR(TRY_CONVERT(date, order_date_dateorders)),
    MONTH(TRY_CONVERT(date, order_date_dateorders))
ORDER BY Order_Year, Order_Month;


/* =========================================================
   3) YEARLY PERFORMANCE
   السؤال:
   - أنهي سنة كانت أفضل؟
   - هل الـ business بينمو سنة عن سنة؟
   ========================================================= */

SELECT
    YEAR(TRY_CONVERT(date, order_date_dateorders)) AS Order_Year,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    COUNT(DISTINCT order_id) AS Total_Orders,
    COUNT(DISTINCT customer_id) AS Customers,
    SUM(order_item_quantity) AS Quantity_Sold
FROM DataCo_Cleaned
GROUP BY YEAR(TRY_CONVERT(date, order_date_dateorders))
ORDER BY Order_Year;


/* =========================================================
   4) MONTH SEASONALITY
   السؤال:
   - هل في شهور معينة الشركة بتبيع فيها أكتر؟
   - بعيدًا عن السنة، أنهي شهر عادةً هو الأقوى؟
   ========================================================= */

SELECT
    MONTH(TRY_CONVERT(date, order_date_dateorders)) AS Month_Number,
    DATENAME(
        MONTH,
        TRY_CONVERT(date, order_date_dateorders)
    ) AS Month_Name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    COUNT(DISTINCT order_id) AS Total_Orders
FROM DataCo_Cleaned
GROUP BY
    MONTH(TRY_CONVERT(date, order_date_dateorders)),
    DATENAME(MONTH, TRY_CONVERT(date, order_date_dateorders))
ORDER BY Month_Number;


/* =========================================================
   5) DEPARTMENT PERFORMANCE
   السؤال:
   - أنهي Department بيجيب أكبر Sales؟
   - أنهي Department بيجيب أكبر Profit؟
   - هل الـ high-sales departments هي نفسها high-profit؟
   ========================================================= */

SELECT
    department_name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Sold,
    COUNT(DISTINCT order_id) AS Total_Orders,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY department_name
ORDER BY Total_Sales DESC;


/* =========================================================
   6) CATEGORY PERFORMANCE
   السؤال:
   - أنهي Category هي الأكثر مبيعًا؟
   - أنهي Category تحقق أكبر Profit؟
   ========================================================= */

SELECT
    category_name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Sold,
    COUNT(DISTINCT order_id) AS Total_Orders,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY category_name
ORDER BY Total_Sales DESC;


/* =========================================================
   7) TOP PRODUCTS BY SALES
   السؤال:
   - إيه المنتجات اللي عليها أكبر طلب؟
   - إيه المنتجات اللي بتجيب أكبر Revenue؟
   ========================================================= */

SELECT TOP 10
    product_name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Sold,
    COUNT(DISTINCT order_id) AS Total_Orders
FROM DataCo_Cleaned
GROUP BY product_name
ORDER BY Total_Sales DESC;


/* =========================================================
   8) TOP PRODUCTS BY PROFIT
   السؤال:
   - مين أهم Products من ناحية Profit مش Sales فقط؟
   ========================================================= */

SELECT TOP 10
    product_name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Sold,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY product_name
ORDER BY Total_Profit DESC;


/* =========================================================
   9) HIGH SALES BUT LOW PROFIT PRODUCTS
   السؤال:
   - إيه المنتجات اللي بتبيع كتير لكن هامش ربحها ضعيف؟
    
   ========================================================= */

SELECT
    product_name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin,
    SUM(order_item_quantity) AS Quantity_Sold
FROM DataCo_Cleaned
GROUP BY product_name
HAVING SUM(sales) > 100000
ORDER BY Profit_Margin ASC;


/* =========================================================
   10) LOW-MARGIN CATEGORIES
   السؤال:
   - أنهي Categories بتبيع كويس لكن بتحقق Margin ضعيف؟
   ========================================================= */

SELECT
    category_name,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY category_name
HAVING SUM(sales) > 50000
ORDER BY Profit_Margin ASC;


/* =========================================================
   11) CUSTOMER SEGMENT PERFORMANCE
   السؤال:
   - Consumer ولا Corporate ولا Home Office؟
   - مين بيشتري أكتر؟
   - مين أكثر ربحية؟
   ========================================================= */

SELECT
    customer_segment,
    COUNT(DISTINCT customer_id) AS Customers,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Sold,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY customer_segment
ORDER BY Total_Sales DESC;


/* =========================================================
   12) REPEAT CUSTOMERS
   السؤال:
   - هل العملاء بيرجعوا يشتروا تاني؟
   - كام % من العملاء Repeat Customers؟
   ========================================================= */

WITH CustomerOrders AS
(
    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS Number_Of_Orders
    FROM DataCo_Cleaned
    GROUP BY customer_id
)
SELECT
    COUNT(*) AS Total_Customers,
    SUM(
        CASE
            WHEN Number_Of_Orders > 1 THEN 1
            ELSE 0
        END
    ) AS Repeat_Customers,
    CAST(
        SUM(
            CASE
                WHEN Number_Of_Orders > 1 THEN 1
                ELSE 0
            END
        ) * 100.0 / COUNT(*)
        AS DECIMAL(10,2)
    ) AS Repeat_Customer_Percentage
FROM CustomerOrders;


/* =========================================================
   13) TOP CUSTOMERS BY REVENUE
   السؤال:
   - مين أهم العملاء من ناحية Revenue؟
   - هل الـ business معتمد على عدد قليل من العملاء؟
   ========================================================= */

SELECT TOP 20
    customer_id,
    customer_segment,
    COUNT(DISTINCT order_id) AS Total_Orders,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Bought
FROM DataCo_Cleaned
GROUP BY
    customer_id,
    customer_segment
ORDER BY Total_Sales DESC;


/* =========================================================
   14) TOP CUSTOMERS BY PROFIT
   السؤال:
   - مين العملاء اللي الشركة بتكسب منهم أكتر؟
   ========================================================= */

SELECT TOP 20
    customer_id,
    customer_segment,
    COUNT(DISTINCT order_id) AS Total_Orders,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit
FROM DataCo_Cleaned
GROUP BY
    customer_id,
    customer_segment
ORDER BY Total_Profit DESC;


/* =========================================================
   15) MARKET PERFORMANCE
   السؤال:
   - أنهي Market هو الأقوى؟
   - وهل أعلى Sales = أعلى Profit؟
   ========================================================= */

SELECT
    market,
    COUNT(DISTINCT order_id) AS Orders,
    COUNT(DISTINCT customer_id) AS Customers,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY market
ORDER BY Total_Sales DESC;


/* =========================================================
   16) TOP COUNTRIES
   السؤال:
   - أنهي الدول هي أكبر أسواق؟
   ========================================================= */

SELECT TOP 15
    order_country,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    SUM(order_item_quantity) AS Quantity_Sold
FROM DataCo_Cleaned
GROUP BY order_country
ORDER BY Total_Sales DESC;


/* =========================================================
   17) TOP ORDER REGIONS
   السؤال:
   - أنهي Region هي الأكثر مبيعًا وربحية؟
   ========================================================= */

SELECT
    order_region,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Total_Sales,
    SUM(order_profit_per_order) AS Total_Profit,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY order_region
ORDER BY Total_Sales DESC;


/* =========================================================
   18) ORDER STATUS ANALYSIS
   السؤال:
   - كام Order Complete؟
   - كام Pending؟
   - كام Canceled؟
   - كام Suspected Fraud؟
   ========================================================= */

SELECT
    order_status,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit,
    SUM(order_item_quantity) AS Quantity
FROM DataCo_Cleaned
GROUP BY order_status
ORDER BY Orders DESC;


/* =========================================================
   19) CANCELED & FRAUD IMPACT
   السؤال:
   - حجم المبيعات المعرضة للخطر بسبب Canceled/Fraud orders؟
   ========================================================= */

SELECT
    order_status,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Potential_Sales_Impact,
    SUM(order_profit_per_order) AS Profit_Impact
FROM DataCo_Cleaned
WHERE order_status IN ('CANCELED', 'SUSPECTED_FRAUD')
GROUP BY order_status
ORDER BY Potential_Sales_Impact DESC;


/* =========================================================
   20) DELIVERY PERFORMANCE
   السؤال:
   - كام % Late؟
   - كام % On Time؟
   - هل مشكلة الشحن كبيرة؟
   ========================================================= */

SELECT
    delivery_status,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    CAST(
        COUNT(DISTINCT order_id) * 100.0 /
        SUM(COUNT(DISTINCT order_id)) OVER ()
        AS DECIMAL(10,2)
    ) AS Order_Percentage
FROM DataCo_Cleaned
GROUP BY delivery_status
ORDER BY Orders DESC;


/* =========================================================
   21) SHIPPING MODE PERFORMANCE
   السؤال:
   - أنهي Shipping Mode أكثر استخدامًا؟
   - أنهي واحدة فيها Late Delivery Risk أعلى؟
   ========================================================= */

SELECT
    shipping_mode,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit,
    AVG(CAST(days_for_shipping_real AS DECIMAL(10,2)))
        AS Avg_Real_Shipping_Days,
    AVG(CAST(days_for_shipment_scheduled AS DECIMAL(10,2)))
        AS Avg_Scheduled_Days,
    AVG(CAST(late_delivery_risk AS DECIMAL(10,2))) * 100
        AS Late_Risk_Percentage
FROM DataCo_Cleaned
GROUP BY shipping_mode
ORDER BY Late_Risk_Percentage DESC;


/* =========================================================
   22) ACTUAL SHIPPING VS SCHEDULED
   السؤال:
   - الشركة بتوصل قبل المعاد ولا بعده؟
   - متوسط التأخير كام يوم؟
   ========================================================= */

 SELECT 
    shipping_mode,
    AVG(CAST(days_for_shipping_real AS DECIMAL(10,2))) AS Avg_Real_Shipping_Days,
    AVG(CAST(days_for_shipment_scheduled AS DECIMAL(10,2))) AS Avg_Scheduled_Days,
    AVG(CAST(days_for_shipping_real AS INT) - CAST(days_for_shipment_scheduled AS INT)) AS Avg_Delay_Days
FROM DataCo_Cleaned
GROUP BY shipping_mode
ORDER BY Avg_Delay_Days DESC;


/* =========================================================
   23) LATE DELIVERY BY MARKET
   السؤال:
   - أنهي Market عنده أكبر مشكلة Delivery؟
   ========================================================= */

SELECT
    market,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(
        CASE
            WHEN late_delivery_risk = 1 THEN 1
            ELSE 0
        END
    ) AS Late_Risk_Rows,
    CAST(
        AVG(CAST(late_delivery_risk AS DECIMAL(10,2))) * 100
        AS DECIMAL(10,2)
    ) AS Late_Risk_Percentage
FROM DataCo_Cleaned
GROUP BY market
ORDER BY Late_Risk_Percentage DESC;


/* =========================================================
   24) LATE DELIVERY BY DEPARTMENT
   السؤال:
   - هل منتجات/Departments معينة بتسبب مشاكل في الشحن؟
   ========================================================= */

SELECT
    department_name,
    COUNT(DISTINCT order_id) AS Orders,
    AVG(CAST(late_delivery_risk AS DECIMAL(10,2))) * 100
        AS Late_Risk_Percentage,
    SUM(sales) AS Sales
FROM DataCo_Cleaned
GROUP BY department_name
ORDER BY Late_Risk_Percentage DESC;


/* =========================================================
   25) DISCOUNT ANALYSIS
   السؤال:
   - هل الخصم العالي مرتبط بربح أقل؟
   - أنهي Discount Range بيحقق أفضل Profit؟
   ========================================================= */

SELECT
    CASE
        WHEN order_item_discount_rate = 0 THEN '0%'
        WHEN order_item_discount_rate <= 0.05 THEN '0%-5%'
        WHEN order_item_discount_rate <= 0.10 THEN '5%-10%'
        WHEN order_item_discount_rate <= 0.20 THEN '10%-20%'
        ELSE '20%+'
    END AS Discount_Band,

    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_item_discount) AS Total_Discount,
    SUM(order_profit_per_order) AS Profit,

    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin

FROM DataCo_Cleaned
GROUP BY
    CASE
        WHEN order_item_discount_rate = 0 THEN '0%'
        WHEN order_item_discount_rate <= 0.05 THEN '0%-5%'
        WHEN order_item_discount_rate <= 0.10 THEN '5%-10%'
        WHEN order_item_discount_rate <= 0.20 THEN '10%-20%'
        ELSE '20%+'
    END
ORDER BY Profit_Margin DESC;


/* =========================================================
   26) PAYMENT TYPE PERFORMANCE
   السؤال:
   - أنهي طريقة دفع هي الأكثر استخدامًا؟
   - وهل طريقة الدفع مرتبطة بالـProfit؟
   ========================================================= */

SELECT
    type AS Payment_Type,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit,
    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin
FROM DataCo_Cleaned
GROUP BY type
ORDER BY Orders DESC;


/* =========================================================
   27) AVERAGE ORDER VALUE
   السؤال:
   - متوسط قيمة الـOrder كام؟
   - ومتوسط عدد المنتجات في الـOrder؟
   ========================================================= */

WITH OrderLevel AS
(
    SELECT
        order_id,
        SUM(sales) AS Order_Sales,
        SUM(order_item_quantity) AS Order_Quantity
    FROM DataCo_Cleaned
    GROUP BY order_id
)
SELECT
    AVG(Order_Sales) AS Average_Order_Value,
    AVG(Order_Quantity) AS Average_Items_Per_Order,
    MAX(Order_Sales) AS Highest_Order_Value,
    MAX(Order_Quantity) AS Largest_Order_Quantity
FROM OrderLevel;


/* =========================================================
   28) LOSS-MAKING ORDERS
   السؤال:
   - كام Order الشركة خسرت فيه؟
   - نسبة الـLoss-Making Orders كام؟
   ========================================================= */

WITH OrderProfit AS
(
    SELECT
        order_id,
        SUM(order_profit_per_order) AS Total_Order_Profit,
        SUM(sales) AS Total_Order_Sales
    FROM DataCo_Cleaned
    GROUP BY order_id
)
SELECT
    COUNT(*) AS Total_Orders,
    SUM(
        CASE
            WHEN Total_Order_Profit < 0 THEN 1
            ELSE 0
        END
    ) AS Loss_Making_Orders,
    CAST(
        SUM(
            CASE
                WHEN Total_Order_Profit < 0 THEN 1
                ELSE 0
            END
        ) * 100.0 / COUNT(*)
        AS DECIMAL(10,2)
    ) AS Loss_Order_Percentage
FROM OrderProfit;


/* =========================================================
   29) PRODUCTS THAT ACTUALLY LOSE MONEY
   السؤال:
   - إيه المنتجات اللي إجمالي ربحها سلبي؟
   - دي Products محتاجة مراجعة Pricing / Discount / Cost.
   ========================================================= */

SELECT
    product_name,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit,
    SUM(order_item_quantity) AS Quantity_Sold
FROM DataCo_Cleaned
GROUP BY product_name
HAVING SUM(order_profit_per_order) < 0
ORDER BY Profit ASC;


/* =========================================================
   30) PRODUCTS WITH HIGH DEMAND
   السؤال:
   - إيه المنتجات اللي عليها أعلى ضغط/طلب؟
   - نستخدمها كـDemand Indicator للمخزون.
   ========================================================= */

SELECT TOP 20
    product_name,
    SUM(order_item_quantity) AS Quantity_Sold,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit
FROM DataCo_Cleaned
GROUP BY product_name
ORDER BY Quantity_Sold DESC;


/* =========================================================
   31) DEMAND BY MONTH FOR PRODUCTS
   السؤال:
   - هل الطلب على المنتجات ثابت ولا بيتغير؟
   - دي مهمة جدًا لو هنفكر في Inventory Planning.
   ========================================================= */

SELECT
    product_name,
    YEAR(TRY_CONVERT(date, order_date_dateorders)) AS Order_Year,
    MONTH(TRY_CONVERT(date, order_date_dateorders)) AS Order_Month,
    SUM(order_item_quantity) AS Quantity_Sold,
    COUNT(DISTINCT order_id) AS Orders
FROM DataCo_Cleaned
GROUP BY
    product_name,
    YEAR(TRY_CONVERT(date, order_date_dateorders)),
    MONTH(TRY_CONVERT(date, order_date_dateorders))
ORDER BY
    product_name,
    Order_Year,
    Order_Month;


/* =========================================================
   32) CUSTOMER CONCENTRATION
   السؤال:
   - هل نسبة صغيرة من العملاء بتجيب نسبة كبيرة من Sales؟
   - مهم جدًا للإدارة: هل الشركة معتمدة على Key Customers؟
   ========================================================= */

WITH CustomerSales AS
(
    SELECT
        customer_id,
        SUM(sales) AS Customer_Sales
    FROM DataCo_Cleaned
    GROUP BY customer_id
),
RankedCustomers AS
(
    SELECT
        customer_id,
        Customer_Sales,
        NTILE(10) OVER (ORDER BY Customer_Sales DESC) AS Customer_Decile
    FROM CustomerSales
)
SELECT
    Customer_Decile,
    COUNT(*) AS Customers,
    SUM(Customer_Sales) AS Sales,
    CAST(
        SUM(Customer_Sales) * 100.0 /
        (SELECT SUM(Customer_Sales) FROM CustomerSales)
        AS DECIMAL(10,2)
    ) AS Sales_Share_Percentage
FROM RankedCustomers
GROUP BY Customer_Decile
ORDER BY Customer_Decile;


/* =========================================================
   33) CUSTOMER COUNTRY VS ORDER COUNTRY
   السؤال الغريب:
   - العملاء مقيمين فين؟
   - وبيطلبوا منين؟
   - هل الشركة بتبيع خارج مكان وجود العملاء؟
   ========================================================= */

SELECT
    customer_country,
    COUNT(DISTINCT customer_id) AS Customers,
    COUNT(DISTINCT order_country) AS Countries_Ordered_From,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales
FROM DataCo_Cleaned
GROUP BY customer_country
ORDER BY Sales DESC;


/* =========================================================
   34) TOP CITIES
   السؤال:
   - أنهي مدن هي أقوى نقاط البيع؟
   ========================================================= */

SELECT TOP 20
    order_city,
    order_country,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit
FROM DataCo_Cleaned
GROUP BY
    order_city,
    order_country
ORDER BY Sales DESC;


/* =========================================================
   35) DAY OF WEEK PERFORMANCE
   السؤال:
   - أنهي أيام الأسبوع فيها Orders أكتر؟
   - ممكن نستخدمها للتسويق والعمليات.
   ========================================================= */

SELECT
    DATENAME(
        WEEKDAY,
        TRY_CONVERT(date, order_date_dateorders)
    ) AS Day_Name,
    COUNT(DISTINCT order_id) AS Orders,
    SUM(sales) AS Sales,
    SUM(order_profit_per_order) AS Profit
FROM DataCo_Cleaned
GROUP BY
    DATENAME(
        WEEKDAY,
        TRY_CONVERT(date, order_date_dateorders)
    )
ORDER BY Orders DESC;


/* =========================================================
   36) DATA QUALITY CHECK
   السؤال:
   - هل في Missing Values في الأعمدة المهمة؟
   - هل في Duplicate Order Item IDs؟
   ========================================================= */

SELECT
    COUNT(*) AS Total_Rows,

    SUM(CASE WHEN order_id IS NULL THEN 1 ELSE 0 END)
        AS Missing_Order_ID,

    SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END)
        AS Missing_Customer_ID,

    SUM(CASE WHEN product_card_id IS NULL THEN 1 ELSE 0 END)
        AS Missing_Product_ID,

    SUM(CASE WHEN sales IS NULL THEN 1 ELSE 0 END)
        AS Missing_Sales,

    SUM(CASE WHEN order_item_quantity IS NULL THEN 1 ELSE 0 END)
        AS Missing_Quantity,

    COUNT(*) - COUNT(DISTINCT order_item_id)
        AS Duplicate_Order_Item_IDs

FROM DataCo_Cleaned;


/* =========================================================
   37) PRODUCT STATUS CHECK
   السؤال:
   - هل عندنا Products Active/Inactive؟
   - هل الـproduct_status مفيد أصلًا للمخزون؟
   ========================================================= */

SELECT
    product_status,
    COUNT(DISTINCT product_card_id) AS Products,
    SUM(order_item_quantity) AS Quantity_Sold,
    SUM(sales) AS Sales
FROM DataCo_Cleaned
GROUP BY product_status
ORDER BY product_status;


/* =========================================================
   38) PRODUCT DEMAND PRESSURE
   السؤال:
   - مين المنتجات اللي عندها High Demand؟
   - نستخدمها كـ Inventory Warning Indicator
     وليس Stock Coverage حقيقي.
   ========================================================= */

SELECT
    product_name,
    SUM(order_item_quantity) AS Total_Quantity_Sold,
    COUNT(DISTINCT order_id) AS Total_Orders,
    COUNT(DISTINCT
        CONVERT(char(7), TRY_CONVERT(date, order_date_dateorders), 120)
    ) AS Active_Months,

    CAST(
        SUM(order_item_quantity) * 1.0 /
        NULLIF(
            COUNT(DISTINCT
                CONVERT(char(7),
                    TRY_CONVERT(date, order_date_dateorders), 120
                )
            ),0
        )
        AS DECIMAL(10,2)
    ) AS Avg_Monthly_Demand

FROM DataCo_Cleaned
GROUP BY product_name
ORDER BY Avg_Monthly_Demand DESC;


/* =========================================================
   39) LOSS-MAKING PRODUCTS WITH HIGH SALES
   السؤال:
   - في Products الشركة بتبيعها كتير
   - لكن بتخسر منها؟
   - دي واحدة من أهم الـRed Flags.
   ========================================================= */

SELECT
    product_name,
    SUM(sales) AS Total_Sales,
    SUM(order_item_quantity) AS Quantity_Sold,
    SUM(order_profit_per_order) AS Total_Profit,

    CAST(
        SUM(order_profit_per_order) * 100.0 /
        NULLIF(SUM(sales),0)
        AS DECIMAL(10,2)
    ) AS Profit_Margin

FROM DataCo_Cleaned
GROUP BY product_name

HAVING
    SUM(sales) > 50000
    AND SUM(order_profit_per_order) < 0

ORDER BY Total_Profit ASC;


/* =========================================================
   40) SHIPPING + PROFIT COMBINATION
   السؤال:
   - هل طرق الشحن المختلفة بتأثر على الربحية؟
   - هل في Shipping Mode غالي/سيئ الأداء؟
   ========================================================= */

SELECT
    shipping_mode,

    COUNT(DISTINCT order_id) AS Orders,

    SUM(sales) AS Sales,

    SUM(order_profit_per_order) AS Profit,

    AVG(
        CAST(days_for_shipping_real AS DECIMAL(10,2))
    ) AS Avg_Actual_Delivery_Days,

    AVG(
        CAST(days_for_shipment_scheduled AS DECIMAL(10,2))
    ) AS Avg_Scheduled_Delivery_Days,

    CAST(
        AVG(CAST(late_delivery_risk AS DECIMAL(10,2))) * 100
        AS DECIMAL(10,2)
    ) AS Late_Risk_Percentage

FROM DataCo_Cleaned
GROUP BY shipping_mode
ORDER BY Late_Risk_Percentage DESC;

