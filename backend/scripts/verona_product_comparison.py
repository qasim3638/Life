"""
Verona Product Comparison Script
Compares products from system database with Verona supplier pricelist
"""
import json
import re
from collections import defaultdict
from datetime import datetime

# Verona Supplier Pricelist (from Excel)
# This is the authoritative list of products Verona sells
SUPPLIER_PRODUCTS = [
    # Porcelain | Ceramic Tiles
    {"sku": "P14461", "name": "Bumpy Beige Wall Tile"},
    {"sku": "P13322", "name": "Bumpy White Wall Tile"},
    {"sku": "P12428", "name": "Glossy White Wall Tile"},
    {"sku": "P12429", "name": "Matt White Wall Tile"},
    {"sku": "P12430", "name": "Bumpy Glossy White Wall Tile"},
    {"sku": "P12431", "name": "Glossy White Wall Tile"},
    {"sku": "P12846", "name": "Etta Bianco Wall Tile"},
    {"sku": "P12847", "name": "Etta Steel Wall Tile"},
    {"sku": "P12848", "name": "Zeta Dove Wall Tile"},
    {"sku": "P12849", "name": "Zeta Silver Wall Tile"},
    {"sku": "P13855", "name": "Bumpy Glossy White Wall Tile"},
    {"sku": "P12436", "name": "White Wall & Floor Tile"},
    {"sku": "P13323", "name": "Bumpy White Wall Tile"},
    {"sku": "P13325", "name": "White Wall Tile"},
    {"sku": "P13493", "name": "Gloss White Wall Tile"},
    {"sku": "P12435", "name": "White Wall & Floor Tile"},
    {"sku": "P12434", "name": "White Wall & Floor Tile"},
    {"sku": "P12438", "name": "Glossy White Wall Tile"},
    {"sku": "P10176", "name": "Metro Bone Wall Tile"},
    {"sku": "P10178", "name": "Metro Sage Wall Tile"},
    {"sku": "P10175", "name": "Metro White Wall Tile"},
    {"sku": "P12439", "name": "Matt White Wall Tile"},
    {"sku": "P10177", "name": "Metro Light Grey Wall Tile"},
    {"sku": "P12844", "name": "Vernazza Bianco Wall Tile"},
    {"sku": "P12845", "name": "Vernazza Décor Wall Tile"},
    {"sku": "P13818", "name": "Bumpy White Wall Tile"},
    {"sku": "P10396", "name": "Central Bone Wall Tile"},
    {"sku": "P10397", "name": "Central Light Grey Wall Tile"},
    {"sku": "P13648", "name": "Central Matt White Wall Tile"},
    {"sku": "P10395", "name": "Central White Wall Tile"},
    {"sku": "P15091", "name": "Bosco Anthracite Wall & Floor Tile"},
    {"sku": "P15094", "name": "Bosco Cream Wall & Floor Tile"},
    {"sku": "P15092", "name": "Bosco Grey Wall & Floor Tile"},
    {"sku": "P15093", "name": "Bosco Mink Wall & Floor Tile"},
    {"sku": "P11625", "name": "Metro Graphite Wall Tile"},
    {"sku": "P14682", "name": "Bosco Anthracite Wall & Floor Tile"},
    {"sku": "P14681", "name": "Bosco Cream Wall & Floor Tile"},
    {"sku": "P14683", "name": "Bosco Grey Wall & Floor Tile"},
    {"sku": "P14680", "name": "Bosco Mink Wall & Floor Tile"},
    {"sku": "P12814", "name": "Elbert Blanco Décor Wall Tile"},
    {"sku": "P12811", "name": "Elbert Blanco Wall Tile"},
    {"sku": "P12812", "name": "Elbert Gris Wall Tile"},
    {"sku": "P12815", "name": "Elbert Marfil Décor Wall Tile"},
    {"sku": "P12813", "name": "Elbert Marfil Wall Tile"},
    {"sku": "P10251", "name": "Metro Dark Grey Wall Tile"},
    {"sku": "P11534", "name": "Metro Turquoise Wall Tile"},
    {"sku": "P12853", "name": "Theodore Gris Décor Wall Tile"},
    {"sku": "P12850", "name": "Theodore Gris Wall Tile"},
    {"sku": "P12852", "name": "Theodore Perla Wall Tile"},
    {"sku": "P13649", "name": "Central Black Matt Wall Tile"},
    {"sku": "P10398", "name": "Central Black Wall Tile"},
    {"sku": "D11204", "name": "Derwent Dark Grey Wall & Floor Tile"},
    {"sku": "D11206", "name": "Derwent Light Grey Wall & Floor Tile"},
    {"sku": "D11208", "name": "Derwent White Wall & Floor Tile"},
    {"sku": "P10179", "name": "Metro Black Wall Tile"},
    {"sku": "P12594", "name": "Sherwood Oak Glazed Wall & Floor Tile"},
    {"sku": "P12593", "name": "Sherwood Smoke Grey Wall & Floor Tile"},
    {"sku": "P12201", "name": "Central Midnight Blue Wall Tile"},
    {"sku": "P10297", "name": "Kendal Bianco Wall & Floor Tile"},
    {"sku": "P11554", "name": "Lamia Grey Wall & Floor Tile"},
    {"sku": "P12883", "name": "Bloomberg Wall Tile"},
    {"sku": "P12884", "name": "Bloomberg Wall Tile"},
    {"sku": "P13002", "name": "Cordelia Wall Tile"},
    {"sku": "P12877", "name": "Goldman Wall Tile"},
    {"sku": "P12878", "name": "Goldman Wall Tile"},
    {"sku": "P14481", "name": "Hampton Beige Wall Tile"},
    {"sku": "P13000", "name": "Hugo Grey Wall Tile"},
    {"sku": "P12881", "name": "Laurent Beige Wall Tile"},
    {"sku": "P12882", "name": "Laurent Beige Wall Tile"},
    {"sku": "P12879", "name": "Laurent Grey Wall Tile"},
    {"sku": "P12880", "name": "Laurent Grey Wall Tile"},
    {"sku": "P13001", "name": "Oscar Wall Tile"},
    {"sku": "P14482", "name": "Vander Grey Wall Tile"},
    {"sku": "P12875", "name": "Waldorf Wall Tile"},
    {"sku": "P12876", "name": "Waldorf Wall Tile"},
    {"sku": "P12035", "name": "Mondrian Charcoal Patterned Wall & Floor Tile"},
    {"sku": "P12033", "name": "Mondrian Navy Blue Patterned Wall & Floor Tile"},
    {"sku": "P12038", "name": "Vincent Grey Patterned Wall & Floor Tile"},
    {"sku": "P12037", "name": "Vincent Navy Blue Patterned Wall & Floor Tile"},
    {"sku": "P12997", "name": "Bloomberg Décor Wall Tile"},
    {"sku": "P12995", "name": "Goldman Décor Wall Tile"},
    {"sku": "P12993", "name": "Laurent Beige Decor Wall Tile"},
    {"sku": "P12994", "name": "Laurent Grey Decor Wall Tile"},
    {"sku": "P12996", "name": "Waldorf Décor Wall Tile"},
    {"sku": "P14289", "name": "Gemstone Avorio Wall Tile"},
    {"sku": "P14290", "name": "Gemstone Geo Avorio Wall Tile"},
    {"sku": "P14292", "name": "Gemstone Geo Grey Wall Tile"},
    {"sku": "P14291", "name": "Gemstone Grey Wall Tile"},
    {"sku": "P14300", "name": "Polesden Art Decor Cream Wall Tile"},
    {"sku": "P14298", "name": "Polesden Art Decor White Wall Tile"},
    {"sku": "P14299", "name": "Polesden Cream Wall Tile"},
    {"sku": "P14297", "name": "Polesden White Wall Tile"},
    {"sku": "P14296", "name": "Cliveden Concept Decor Grey Wall Tile"},
    {"sku": "P14295", "name": "Cliveden Concept Decor White Wall Tile"},
    {"sku": "P14294", "name": "Cliveden Grey Wall Tile"},
    {"sku": "P14293", "name": "Cliveden White Wall Tile"},
    {"sku": "P10300", "name": "Metro Calacatta Wall Tile"},
    {"sku": "P11559", "name": "Metro Black Wall Tile"},
    {"sku": "P11546", "name": "Metro Bone Wall Tile"},
    {"sku": "P11545", "name": "Metro Dark Grey Wall Tile"},
    {"sku": "P11626", "name": "Metro Graphite Wall Tile"},
    {"sku": "P11542", "name": "Metro Light Grey Wall Tile"},
    {"sku": "P12856", "name": "George Arena Wall Tile"},
    {"sku": "P12855", "name": "George Perla Wall Tile"},
    {"sku": "P11407", "name": "Monteverde Oak Wall & Floor Tile"},
    {"sku": "P11406", "name": "Monteverde Smoke Wall & Floor Tile"},
    {"sku": "P11408", "name": "Monteverde Walnut Wall & Floor Tile"},
    {"sku": "P11405", "name": "Monteverde White Birch Wall & Floor Tile"},
    {"sku": "P13650", "name": "Central Gloss White Wall Tile"},
    {"sku": "P13652", "name": "Central Matt White Wall Tile"},
    {"sku": "P11541", "name": "Metro White Wall Tile"},
    {"sku": "P10963", "name": "Anderley Dark Grey Wall & Floor Tile"},
    {"sku": "P10965", "name": "Anderley Dark Grey Wall & Floor Tile"},
    {"sku": "P10962", "name": "Anderley Dark Grey Wall & Floor Tile"},
    {"sku": "P10964", "name": "Anderley Dark Grey Wall & Floor Tile"},
    {"sku": "P10959", "name": "Anderley Light Grey Wall & Floor Tile"},
    {"sku": "P10961", "name": "Anderley Light Grey Wall & Floor Tile"},
    {"sku": "P10958", "name": "Anderley Light Grey Wall & Floor Tile"},
    {"sku": "P10960", "name": "Anderley Light Grey Wall & Floor Tile"},
    {"sku": "P12697", "name": "Aphrodite Emerald Wall & Floor Tile"},
    {"sku": "P12686", "name": "Apollo Grey Wall & Floor Tile"},
    {"sku": "P12691", "name": "Artemis Stone Wall & Floor Tile"},
    {"sku": "P12684", "name": "Athena Pearl Wall & Floor Tile"},
    {"sku": "P12616", "name": "Hannah Wall & Floor Tile"},
    {"sku": "P12614", "name": "Hannah Wall & Floor Tile"},
    {"sku": "P12615", "name": "Hannah Wall & Floor Tile"},
    {"sku": "P12613", "name": "Hannah Wall & Floor Tile"},
    {"sku": "P12694", "name": "Hera Marble Wall & Floor Tile"},
    {"sku": "P12698", "name": "Hestia Viola Marble Wall & Floor Tile"},
    {"sku": "P12689", "name": "Kore Slate Grey Wall & Floor Tile"},
    {"sku": "P12681", "name": "Zeus Midnight Black Wall & Floor Tile"},
    {"sku": "P13517", "name": "Bloomberg Wall & Floor Tile"},
    {"sku": "P12950", "name": "Goldman Wall & Floor Tile"},
    {"sku": "P13515", "name": "Laurent Beige Wall & Floor Tile"},
    {"sku": "P13516", "name": "Laurent Grey Wall & Floor Tile"},
    {"sku": "P13514", "name": "Waldorf Wall & Floor Tile"},
    {"sku": "P12687", "name": "Apollo Grey Wall & Floor Tile"},
    {"sku": "P12692", "name": "Artemis Stone Wall & Floor Tile"},
    {"sku": "P12787", "name": "Capri Dark Wall Tile"},
    {"sku": "P12695", "name": "Hera Marble Wall & Floor Tile"},
    {"sku": "P12690", "name": "Kore Slate Grey Wall & Floor Tile"},
    {"sku": "P10614", "name": "Space Grey Wall & Floor Tile"},
    {"sku": "P10613", "name": "Space Grey Wall & Floor Tile"},
    {"sku": "P10612", "name": "Space White Wall & Floor Tile"},
    {"sku": "P10611", "name": "Space White Wall & Floor Tile"},
    {"sku": "P10610", "name": "Valletta Statuario Wall & Floor Tile"},
    {"sku": "P10609", "name": "Valletta Statuario Wall & Floor Tile"},
    {"sku": "P12779", "name": "Garonne Moon Lined Wall Tile"},
    {"sku": "P12775", "name": "Garonne Moon Wall Tile"},
    {"sku": "P12780", "name": "Garonne Smoke Lined Wall Tile"},
    {"sku": "P12776", "name": "Garonne Smoke Wall Tile"},
    # Mosaics
    {"sku": "P12904", "name": "Linear Blue Gloss Wall Mosaic"},
    {"sku": "P12396", "name": "Montclair Porcelain Mosaic"},
    {"sku": "P10389", "name": "Rockies New Mexico Porcelain Mosaic"},
    {"sku": "P10387", "name": "Rockies Montana Porcelain Mosaic"},
    {"sku": "P10388", "name": "Rockies Alberta Porcelain Mosaic"},
    # Natural Stone Mosaics
    {"sku": "S20004", "name": "Anatolian Grey Travertine Mosaic"},
    {"sku": "S20143", "name": "Bari White Marble & Mother of Pearl Mosaic"},
    {"sku": "S20116", "name": "Coffee Stone Hexagon Marble Mosaic"},
    {"sku": "S20011W", "name": "Emperador Mix Marble Mosaic"},
    {"sku": "S20013", "name": "Expresso Marble Mosaic"},
    {"sku": "S20115", "name": "Fog Stone Hexagon Marble Mosaic"},
    {"sku": "S20117", "name": "Midnight Stone Hexagon Marble Mosaic"},
    {"sku": "S20105", "name": "Riverstone Black Pebble Mosaic"},
    {"sku": "S20106", "name": "Riverstone White Pebble Mosaic"},
    {"sku": "S20003W", "name": "Silver Grey Travertine Brick Mosaic"},
    {"sku": "S20029", "name": "Silver Shadow Grey Marble Mosaic"},
    {"sku": "S20124", "name": "Vanilla Cream Mix Finish Marble Hexagon Mosaic"},
    # Glass | Mixed Mosaics
    {"sku": "G30224", "name": "Ashby Grey Glass & Metal Mix Offset Linear Mosaic"},
    {"sku": "G30108", "name": "Atlas Fusion Glass/Metal Mix Mosaic 23x23mm"},
    {"sku": "G30223", "name": "Castell Grey Stone & Metal Mix Brick Mosaic 23x48mm"},
    {"sku": "G30134", "name": "Cedar Grey Glass/Stone/Metal Mix Mosaic 15x15mm"},
    {"sku": "G30201", "name": "Chrome Copper Glass & Metal Linear Mix Size Mosaic"},
    {"sku": "G30086W", "name": "Cream Glass/Stone/Metal/Pearl Mix Mini Brick Mosaic 15x30mm"},
    {"sku": "G30209", "name": "Creswell Grey Stone & Metal Mix Linear Mosaic 15x48mm"},
    {"sku": "G30241", "name": "Dusk Grey Herringbone Glass & Mirror Mosaic 15x30mm"},
    {"sku": "G30063", "name": "Emperador Cream Glass/Stone Mix Mosaic 23x23mm"},
    {"sku": "G30039", "name": "Hammered Pearl Aqua Glass Mosaic 23x23mm"},
    {"sku": "G30210", "name": "Heydon Beige Mix Stone/Glass & Metal Linear Mosaic 15x48mm"},
    {"sku": "G30237", "name": "Horizon Silver Wood Effect Glass Brick Mosaic 48x98mm"},
    {"sku": "G30227", "name": "Hutton White/Silver Glass & Stone Mix Mosaic 23x23mm"},
    {"sku": "G30142", "name": "Iridescent Glass/Stone/Metal Mix Modular Mosaic"},
    {"sku": "G30145", "name": "Iridescent Glass/Stone/Metal Mix Mosaic 23x23mm"},
    {"sku": "G30225", "name": "Kenton Grey Glass/Stone/Metal Mix Offset Linear Mosaic"},
    {"sku": "G30226", "name": "Kenton Silver Glass/Stone/Metal Mix Offset Linear Mosaic"},
    {"sku": "G30239", "name": "Lumiere Bevel Antique Mirror Brick Mosaic 75x150mm"},
    {"sku": "G30238", "name": "Lumiere Bevel Mirror Brick Mosaic 75x150mm"},
    {"sku": "G30097", "name": "Moonlight Glass/Metal Mix Modular Mosaic"},
    {"sku": "G30106", "name": "New York Beige Glass/Stone/ Metal Mix Mini Brick Mosaic 15x30mm"},
    {"sku": "G30240", "name": "Pence Copper Herringbone Glass & Stone Mosaic 15x30mm"},
    {"sku": "G30135", "name": "Platinum Glass/Metal Mix Mosaic 15x15mm"},
    {"sku": "G30139", "name": "Platinum Lancer Glass/Metal Mix Mini Brick Mosaic 15x30mm"},
    {"sku": "G30170", "name": "Salvador Grey Stone/Glass Angular Mix Mosaic"},
    {"sku": "G30141", "name": "Saturn Silver Glass/Metal Mix Modular Mosaic"},
    # Outdoor Porcelain
    {"sku": "P13568", "name": "Atlanta Black Wall & Floor Tile"},
    {"sku": "P13569", "name": "Atlanta Cream Wall & Floor Tile"},
    {"sku": "P13567", "name": "Atlanta Grey Wall & Floor Tile"},
    {"sku": "P13566", "name": "Atlanta White Wall & Floor Tile"},
    {"sku": "P12659", "name": "Baslow Black Floor Tile"},
    {"sku": "P13767", "name": "Brit Stone Black Floor Tile"},
    {"sku": "P13809", "name": "Brit Stone Grey Floor Tile"},
    {"sku": "P13808", "name": "Brit Stone White Floor Tile"},
    {"sku": "P13810", "name": "Canyon Stone Grey Floor Tile"},
    {"sku": "P13826", "name": "Cement Black Floor Tile"},
    {"sku": "P13773", "name": "Cement Grey Floor Tile"},
    {"sku": "P13770", "name": "Cement White Floor Tile"},
    {"sku": "P12662", "name": "Eyam Beige Floor Tile"},
    {"sku": "P12936", "name": "Loft Ash Floor Tile"},
    {"sku": "P12937", "name": "Loft Grey Floor Tile"},
    {"sku": "P12938", "name": "Loft Taupe Floor Tile"},
    {"sku": "P14595", "name": "Minster Black Edging Floor Tile"},
    {"sku": "P12870", "name": "Rainton Beige Floor Tile"},
    {"sku": "P12817", "name": "Rainton Light Grey Floor Tile"},
    {"sku": "P12664", "name": "Wilsden Slate Black Floor Tile"},
    # ClickLux SPC Flooring
    {"sku": "L10096", "name": "Premium Ash Grey"},
    {"sku": "L10097", "name": "Premium Light Birch"},
    {"sku": "L10098", "name": "Premium Light Oak"},
    {"sku": "L10095", "name": "Premium Limed Beech"},
    {"sku": "L10099", "name": "Premium Natural Oak"},
    {"sku": "L10100", "name": "Premium Warm Chestnut"},
    {"sku": "L10001", "name": "Golden Beech"},
    {"sku": "L10002", "name": "Black Elm"},
    {"sku": "L10003", "name": "Weathered Ash"},
    {"sku": "L10004", "name": "Rich Walnut"},
    {"sku": "L10005", "name": "Light Oak"},
    {"sku": "L10006", "name": "Rustic Willow"},
    {"sku": "L10007", "name": "Silver Birch"},
    {"sku": "L10008", "name": "Warm Maple"},
    {"sku": "L10009", "name": "Antique Cedar"},
    {"sku": "L10010", "name": "Limed Oak"},
    {"sku": "L10050", "name": "Burnham Golden Oak Heringbone"},
    {"sku": "L10051", "name": "Rydal Natural Oak Heringbone"},
    {"sku": "L10052", "name": "Selwood Light Oak Heringbone"},
    {"sku": "L10053", "name": "Ashdown Limed Oak Heringbone"},
    {"sku": "L10054", "name": "Wyre Silver Oak Heringbone"},
    {"sku": "L10055", "name": "Haldon Antique Oak Heringbone"},
    {"sku": "L10013", "name": "Castello Marble White Tile"},
    {"sku": "L10014", "name": "Pinnacle Concrete Grey Tile"},
    {"sku": "L10015", "name": "Pinnacle Concrete Anthracite Tile"},
    {"sku": "L10016", "name": "Axia Concrete Grey Tile"},
    {"sku": "L10017", "name": "Axia Concrete Anthracite Tile"},
    {"sku": "L10018", "name": "Chamonix Marble Beige Tile"},
    {"sku": "L10021", "name": "Bowfell Stone Grey Tile"},
    {"sku": "L10024", "name": "Rodellar Stone Silver Tile"},
    # Flooring Accessories
    {"sku": "L10085", "name": "16mm SPC Scotia Golden Beech"},
    {"sku": "L10086", "name": "16mm SPC Scotia Walnut"},
    {"sku": "L10087", "name": "16mm SPC Scotia Antique"},
    {"sku": "L10088", "name": "16mm SPC Scotia Silver"},
    {"sku": "L10089", "name": "16mm SPC Scotia Black"},
    {"sku": "L10090", "name": "16mm SPC Scotia Warm Oak"},
    {"sku": "L10091", "name": "16mm SPC Scotia Light Oak"},
    {"sku": "L10092", "name": "16mm SPC Natural Oak"},
    {"sku": "L10093", "name": "16mm SPC Scotia Plain Grey"},
    {"sku": "L10094", "name": "16mm SPC Scotia Plain White"},
    {"sku": "A14262", "name": "SPC Threshold Golden Beech"},
    {"sku": "A14263", "name": "SPC Threshold Walnut"},
    {"sku": "A14264", "name": "SPC Threshold Antique"},
    {"sku": "A14265", "name": "SPC Threshold Silver"},
    {"sku": "A14266", "name": "SPC Threshold Black"},
    {"sku": "A14267", "name": "SPC Threshold Warm Oak"},
    {"sku": "A14268", "name": "SPC Threshold Light Oak"},
    {"sku": "A14269", "name": "SPC Threshold Natural Oak"},
    {"sku": "A14270", "name": "SPC Threshold Plain Grey"},
    {"sku": "A14271", "name": "SPC Threshold Plain White"},
    {"sku": "A14272", "name": "SPC Radiator Pipe Collar Golden Beech"},
    {"sku": "A14273", "name": "SPC Radiator Pipe Collar Walnut"},
    {"sku": "A14274", "name": "SPC Radiator Pipe Collar Antique"},
    {"sku": "A14275", "name": "SPC Radiator Pipe Collar Silver"},
    {"sku": "A14276", "name": "SPC Radiator Pipe Collar Black"},
    {"sku": "A14277", "name": "SPC Radiator Pipe Collar Warm Oak"},
    {"sku": "A14278", "name": "SPC Radiator Pipe Collar Light Oak"},
    {"sku": "A14279", "name": "SPC Radiator Pipe Collar Natural Oak"},
    {"sku": "A14280", "name": "SPC Radiator Pipe Collar Plain Grey"},
    {"sku": "A14281", "name": "SPC Radiator Pipe Collar Plain White"},
    # Accessories
    {"sku": "A10956", "name": "Instarmac"},
    {"sku": "A10201", "name": "Instarmac"},
    {"sku": "A10202", "name": "Instarmac"},
    {"sku": "A10203", "name": "Instarmac"},
    {"sku": "A10828", "name": "Instarmac® ProPave Grout Pebble Grey"},
    {"sku": "A10767", "name": "Instarmac® Ultra ProFlex SPES Grey"},
    {"sku": "A10768", "name": "Instarmac® Ultra ProFlex SPES White"},
    {"sku": "A10765", "name": "Instarmac® Ultra Proflex SP Grey"},
    {"sku": "A10766", "name": "Instarmac® Ultra ProFlex SP White"},
    {"sku": "A10771", "name": "Instarmac® Ultra ProFlex S2 Grey"},
    {"sku": "A10853", "name": "Instarmac® Ultra ProSuper Grip D1TE"},
    {"sku": "A10847", "name": "Instarmac® Ultra ProGrout Flexible Grey"},
    {"sku": "A10848", "name": "Instarmac® Ultra ProGrout White"},
    {"sku": "A14219", "name": "Instarmac® Ultra ProGrout Brilliant White"},
    {"sku": "A10774", "name": "Instarmac® Ultra ProGrout Flexible Jasmine"},
    {"sku": "A10849", "name": "Instarmac® Ultra ProGrout Flexible Limestone"},
    {"sku": "A10837", "name": "Instarmac® Ultra ProGrout Flexible Charcoal"},
    {"sku": "A10838", "name": "Instarmac® ultra ProGrout Flexible Silver Grey"},
    {"sku": "A10776", "name": "Instarmac® Ultra ProGrout Flexible Grey"},
    {"sku": "A10779", "name": "Instarmac® Ultra ProSealer White"},
    {"sku": "A10780", "name": "Instarmac® Ultra ProSealer Jasmine"},
    {"sku": "A10850", "name": "Instarmac® Ultra ProSealer Limestone"},
    {"sku": "A10783", "name": "Instarmac® Ultra ProSealer Charcoal"},
    {"sku": "A10781", "name": "Instarmac® Ultra ProSealer Silver Grey"},
    {"sku": "A10782", "name": "Instarmac® Ultra ProSealer Grey"},
    {"sku": "A10772", "name": "Instarmac® Ultra ProLevel Fibre"},
    {"sku": "A10851", "name": "Instarmac® Ultra ProPrimer"},
    {"sku": "A10852", "name": "Instarmac® Ultra Pro ProPrimer"},
    {"sku": "A10959", "name": "Instarmac® ProGrout Flowable Limestone"},
    {"sku": "A10960", "name": "Instarmac® ProGrout Flowable Silver"},
    {"sku": "A10962", "name": "Instarmac® ProGrout Flowable Grey"},
    {"sku": "A10963", "name": "Instarmac® ProGrout Flowable Charcoal"},
    {"sku": "A14185", "name": "Rubi Cyclone Levelling system Kit"},
    {"sku": "A14186", "name": "Rubi Cyclone Levelling system Kit"},
    {"sku": "A14193", "name": "Rubi Cyclone Flat Base Spin Levelling System"},
    {"sku": "A10834", "name": "Rubi Cyclone Flat Base Spin Levelling System"},
    {"sku": "A14195", "name": "Rubi Cyclone Levelling System Caps"},
    {"sku": "A10122", "name": "Small Self Levelling Pedestal"},
    {"sku": "A10123", "name": "Medium Self Levelling Pedestal"},
    {"sku": "A10125", "name": "PP Pedestal Edging Base & Head Clip"},
    {"sku": "A10126", "name": "PP Pedestal Corner Base & Head Clip"},
    {"sku": "A10127", "name": "PP Pedestal Height Adjustment Key"},
    {"sku": "A10711", "name": "PP Pedestal Wall Clip PCC/03"},
    # ProBacker
    {"sku": "A10840", "name": "ProBacker"},
    {"sku": "A12144", "name": "Pro Backer Cement Backer Board 600x1200x6mm - Half Pallet"},
    {"sku": "A10084", "name": "ProBacker"},
    {"sku": "A12415", "name": "Pro Backer Cement Backer Board 800x1200x12mm - Half Pallet"},
    # MosaicFix
    {"sku": "D10419", "name": "MosaicFix"},
]

# Create a lookup by name (normalized)
def normalize_name(name):
    """Normalize product name for comparison"""
    if not name:
        return ""
    # Convert to lowercase
    name = name.lower()
    # Remove special characters
    name = re.sub(r'[^\w\s]', '', name)
    # Remove extra spaces
    name = ' '.join(name.split())
    return name

def main():
    # Build supplier lookup
    supplier_by_sku = {p['sku']: p for p in SUPPLIER_PRODUCTS}
    supplier_by_name = {}
    for p in SUPPLIER_PRODUCTS:
        norm_name = normalize_name(p['name'])
        if norm_name not in supplier_by_name:
            supplier_by_name[norm_name] = []
        supplier_by_name[norm_name].append(p)
    
    # System products from PDF (sample - you would load all from the actual extraction)
    # This is a condensed version - the full data is in the extraction
    
    print("=" * 80)
    print("VERONA PRODUCT COMPARISON REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    print()
    print(f"Total products in Verona Pricelist (Excel): {len(SUPPLIER_PRODUCTS)}")
    print()
    
    # Summary of supplier categories
    categories = defaultdict(int)
    for p in SUPPLIER_PRODUCTS:
        sku = p['sku']
        if sku.startswith('P'):
            categories['Porcelain/Ceramic'] += 1
        elif sku.startswith('S'):
            categories['Natural Stone Mosaic'] += 1
        elif sku.startswith('G'):
            categories['Glass/Mixed Mosaic'] += 1
        elif sku.startswith('L'):
            categories['Flooring (ClickLux SPC)'] += 1
        elif sku.startswith('A'):
            categories['Accessories'] += 1
        elif sku.startswith('D'):
            categories['Other (D-prefix)'] += 1
    
    print("Supplier Product Categories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count} products")
    print()
    
    return supplier_by_sku, supplier_by_name

if __name__ == "__main__":
    main()
