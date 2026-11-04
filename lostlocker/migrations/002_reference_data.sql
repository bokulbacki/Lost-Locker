-- Reference data carried over from the original scriptsql.txt, with these fixes:
--   * two Locations shared id 609 -> "Other/Unknown" is now 610 (and the "Unkown" typo is fixed)
--   * "Apple" was listed twice as a device brand (132 and 135) -> only 132 is kept
--   * "Other/Unknown" brand (123) is now offered for every item type that has a brand
--   * every item type now offers the "Other/Unknown" location

INSERT INTO itemtype (itemtype_id, itemtype, requires_title) VALUES
    (1, 'Clothing',           false),
    (2, 'Bottle',             false),
    (3, 'Device',             false),
    (4, 'Backpack/Bag/Purse', false),
    (5, 'Book',               true);

INSERT INTO attributetype (attributetype_id, attributetype, description) VALUES
    -- Brands: clothing
    (101, 'Brand', 'Lulu'), (102, 'Brand', 'Stussy'), (103, 'Brand', 'Levis'),
    (104, 'Brand', 'Flojo'), (105, 'Brand', 'Nike'), (106, 'Brand', 'Adidas'),
    (107, 'Brand', 'Polo'), (108, 'Brand', 'Hanes'), (109, 'Brand', 'Fruit of the Loom'),
    (110, 'Brand', 'Wrangler'), (111, 'Brand', 'Under Armour'), (112, 'Brand', 'Patagonia'),
    (113, 'Brand', 'Old Navy'), (114, 'Brand', 'Champion'), (115, 'Brand', 'North Face'),
    (116, 'Brand', 'Vuori'), (117, 'Brand', 'Vans'), (118, 'Brand', 'Gap'),
    (119, 'Brand', 'H&M'), (120, 'Brand', 'Urban Outfitters'), (121, 'Brand', 'REI'),
    (122, 'Brand', 'Helly Hansen'), (123, 'Brand', 'Other/Unknown'),
    -- Brands: bottles
    (124, 'Brand', 'Hydro Flask'), (125, 'Brand', 'Camelbak'), (126, 'Brand', 'Yeti'),
    (127, 'Brand', 'Klean Kanteen'), (128, 'Brand', 'Brita'), (129, 'Brand', 'Nalgene'),
    (130, 'Brand', 'Contigo'), (131, 'Brand', 'Stanley'),
    -- Brands: devices
    (132, 'Brand', 'Apple'), (133, 'Brand', 'Samsung'), (134, 'Brand', 'Google'),
    (136, 'Brand', 'Sony'), (137, 'Brand', 'HP'), (138, 'Brand', 'Garmin'),
    (139, 'Brand', 'Microsoft'),
    -- Brands: bags
    (140, 'Brand', 'Jansport'), (141, 'Brand', 'Herschel'), (142, 'Brand', 'Fjallraven'),
    (143, 'Brand', 'Osprey'),

    (201, 'Color', 'Red'), (202, 'Color', 'Blue'), (203, 'Color', 'Yellow'),
    (204, 'Color', 'White'), (205, 'Color', 'Black'), (206, 'Color', 'Brown'),
    (207, 'Color', 'Green'), (208, 'Color', 'Purple'), (209, 'Color', 'Pink'),
    (210, 'Color', 'Clear'), (211, 'Color', 'Other'), (212, 'Color', 'Grey'),
    (213, 'Color', 'Orange'), (214, 'Color', 'Beige'), (215, 'Color', 'Gold'),
    (216, 'Color', 'Silver'), (217, 'Color', 'Wood'),

    (301, 'ClothingType', 'Shirt'), (302, 'ClothingType', 'Sweater'),
    (303, 'ClothingType', 'Hat'), (304, 'ClothingType', 'Pants'),
    (305, 'ClothingType', 'Shoes'), (306, 'ClothingType', 'Glasses/Sunglasses'),
    (307, 'ClothingType', 'Other'),

    (401, 'Model', 'iPhone'), (402, 'Model', 'iPad'), (403, 'Model', 'Mac'),
    (404, 'Model', 'Apple Watch'), (405, 'Model', 'Airpods'), (406, 'Model', 'S3'),
    (407, 'Model', 'Pixel'), (408, 'Model', 'Galaxy'), (409, 'Model', 'Galaxy Tablet'),
    (410, 'Model', 'Surface'), (411, 'Model', 'Other'),

    (501, 'Size', 'XL'), (502, 'Size', 'Large'), (503, 'Size', 'Medium'),
    (504, 'Size', 'Small'), (505, 'Size', 'XS'), (506, 'Size', '32oz'),
    (507, 'Size', '16oz'), (508, 'Size', '64oz'), (509, 'Size', 'Other/Unknown'),

    (601, 'Location', 'Tram'), (602, 'Location', 'Copley Library'),
    (603, 'Location', 'SLP'), (604, 'Location', 'KSB'), (605, 'Location', 'Saints Hall'),
    (606, 'Location', 'KIPJ'), (607, 'Location', 'Maher'), (608, 'Location', 'Camino'),
    (609, 'Location', 'Founders'), (610, 'Location', 'Other/Unknown'),

    (701, 'Stickers', 'Yes'), (702, 'Stickers', 'No'),

    (801, 'Cap Type', 'Nozzle Lid'), (802, 'Cap Type', 'Straw Lid'),
    (803, 'Cap Type', 'Squirt Lid'), (804, 'Cap Type', 'Flat Screw On');

-- Which attribute values each item type offers.
INSERT INTO item_attribute (itemtype_id, attributetype_id)
SELECT 1, g FROM (                                    -- Clothing
    SELECT generate_series(101, 123) AS g UNION ALL
    SELECT generate_series(141, 143)      UNION ALL   -- (carried over: bag brands offered here too)
    SELECT generate_series(201, 217)      UNION ALL
    SELECT generate_series(301, 307)      UNION ALL
    SELECT generate_series(501, 505)      UNION ALL
    SELECT 509                            UNION ALL
    SELECT generate_series(601, 610)
) clothing;

INSERT INTO item_attribute (itemtype_id, attributetype_id)
SELECT 2, g FROM (                                    -- Bottle
    SELECT generate_series(123, 131) AS g UNION ALL
    SELECT generate_series(201, 217)      UNION ALL
    SELECT generate_series(506, 509)      UNION ALL
    SELECT generate_series(601, 610)      UNION ALL
    SELECT generate_series(701, 702)      UNION ALL
    SELECT generate_series(801, 804)
) bottle;

INSERT INTO item_attribute (itemtype_id, attributetype_id)
SELECT 3, g FROM (                                    -- Device
    SELECT 123 AS g                       UNION ALL
    SELECT generate_series(132, 134)      UNION ALL
    SELECT generate_series(136, 139)      UNION ALL
    SELECT generate_series(401, 411)      UNION ALL
    SELECT generate_series(601, 610)      UNION ALL
    SELECT generate_series(701, 702)
) device;

INSERT INTO item_attribute (itemtype_id, attributetype_id)
SELECT 4, g FROM (                                    -- Backpack/Bag/Purse
    SELECT unnest(ARRAY[101, 106, 111, 112, 115, 117, 123]) AS g UNION ALL
    SELECT generate_series(140, 143)      UNION ALL
    SELECT generate_series(201, 217)      UNION ALL
    SELECT generate_series(601, 610)
) bag;

INSERT INTO item_attribute (itemtype_id, attributetype_id)
SELECT 5, g FROM (                                    -- Book
    SELECT generate_series(201, 217) AS g UNION ALL
    SELECT generate_series(601, 610)      UNION ALL
    SELECT generate_series(701, 702)
) book;
