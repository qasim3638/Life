"""
Verona Product Comparison Report Generator
Compares products from your system (PDF) with Verona supplier pricelist (Excel)
Generates an Excel report with color-coded sections
"""
import re
from datetime import datetime
import xlsxwriter

# ============================================================================
# DATA FROM VERONA SUPPLIER PRICELIST (Excel - Authoritative Source)
# ============================================================================
SUPPLIER_PRODUCTS = [
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
    {"sku": "P12904", "name": "Linear Blue Gloss Wall Mosaic"},
    {"sku": "P12396", "name": "Montclair Porcelain Mosaic"},
    {"sku": "P10389", "name": "Rockies New Mexico Porcelain Mosaic"},
    {"sku": "P10387", "name": "Rockies Montana Porcelain Mosaic"},
    {"sku": "P10388", "name": "Rockies Alberta Porcelain Mosaic"},
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
    {"sku": "G30224", "name": "Ashby Grey Glass & Metal Mix Offset Linear Mosaic"},
    {"sku": "G30108", "name": "Atlas Fusion Glass/Metal Mix Mosaic"},
    {"sku": "G30223", "name": "Castell Grey Stone & Metal Mix Brick Mosaic"},
    {"sku": "G30134", "name": "Cedar Grey Glass/Stone/Metal Mix Mosaic"},
    {"sku": "G30201", "name": "Chrome Copper Glass & Metal Linear Mix Size Mosaic"},
    {"sku": "G30086W", "name": "Cream Glass/Stone/Metal/Pearl Mix Mini Brick Mosaic"},
    {"sku": "G30209", "name": "Creswell Grey Stone & Metal Mix Linear Mosaic"},
    {"sku": "G30241", "name": "Dusk Grey Herringbone Glass & Mirror Mosaic"},
    {"sku": "G30063", "name": "Emperador Cream Glass/Stone Mix Mosaic"},
    {"sku": "G30039", "name": "Hammered Pearl Aqua Glass Mosaic"},
    {"sku": "G30210", "name": "Heydon Beige Mix Stone/Glass & Metal Linear Mosaic"},
    {"sku": "G30237", "name": "Horizon Silver Wood Effect Glass Brick Mosaic"},
    {"sku": "G30227", "name": "Hutton White/Silver Glass & Stone Mix Mosaic"},
    {"sku": "G30142", "name": "Iridescent Glass/Stone/Metal Mix Modular Mosaic"},
    {"sku": "G30145", "name": "Iridescent Glass/Stone/Metal Mix Mosaic"},
    {"sku": "G30225", "name": "Kenton Grey Glass/Stone/Metal Mix Offset Linear Mosaic"},
    {"sku": "G30226", "name": "Kenton Silver Glass/Stone/Metal Mix Offset Linear Mosaic"},
    {"sku": "G30239", "name": "Lumiere Bevel Antique Mirror Brick Mosaic"},
    {"sku": "G30238", "name": "Lumiere Bevel Mirror Brick Mosaic"},
    {"sku": "G30097", "name": "Moonlight Glass/Metal Mix Modular Mosaic"},
    {"sku": "G30106", "name": "New York Beige Glass/Stone/Metal Mix Mini Brick Mosaic"},
    {"sku": "G30240", "name": "Pence Copper Herringbone Glass & Stone Mosaic"},
    {"sku": "G30135", "name": "Platinum Glass/Metal Mix Mosaic"},
    {"sku": "G30139", "name": "Platinum Lancer Glass/Metal Mix Mini Brick Mosaic"},
    {"sku": "G30170", "name": "Salvador Grey Stone/Glass Angular Mix Mosaic"},
    {"sku": "G30141", "name": "Saturn Silver Glass/Metal Mix Modular Mosaic"},
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
    {"sku": "L10050", "name": "Burnham Golden Oak Herringbone"},
    {"sku": "L10051", "name": "Rydal Natural Oak Herringbone"},
    {"sku": "L10052", "name": "Selwood Light Oak Herringbone"},
    {"sku": "L10053", "name": "Ashdown Limed Oak Herringbone"},
    {"sku": "L10054", "name": "Wyre Silver Oak Herringbone"},
    {"sku": "L10055", "name": "Haldon Antique Oak Herringbone"},
    {"sku": "L10013", "name": "Castello Marble White Tile"},
    {"sku": "L10014", "name": "Pinnacle Concrete Grey Tile"},
    {"sku": "L10015", "name": "Pinnacle Concrete Anthracite Tile"},
    {"sku": "L10016", "name": "Axia Concrete Grey Tile"},
    {"sku": "L10017", "name": "Axia Concrete Anthracite Tile"},
    {"sku": "L10018", "name": "Chamonix Marble Beige Tile"},
    {"sku": "L10021", "name": "Bowfell Stone Grey Tile"},
    {"sku": "L10024", "name": "Rodellar Stone Silver Tile"},
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
    {"sku": "A10956", "name": "Instarmac"},
    {"sku": "A10201", "name": "Instarmac"},
    {"sku": "A10202", "name": "Instarmac"},
    {"sku": "A10203", "name": "Instarmac"},
    {"sku": "A10828", "name": "Instarmac ProPave Grout Pebble Grey"},
    {"sku": "A10767", "name": "Instarmac Ultra ProFlex SPES Grey"},
    {"sku": "A10768", "name": "Instarmac Ultra ProFlex SPES White"},
    {"sku": "A10765", "name": "Instarmac Ultra Proflex SP Grey"},
    {"sku": "A10766", "name": "Instarmac Ultra ProFlex SP White"},
    {"sku": "A10771", "name": "Instarmac Ultra ProFlex S2 Grey"},
    {"sku": "A10853", "name": "Instarmac Ultra ProSuper Grip D1TE"},
    {"sku": "A10847", "name": "Instarmac Ultra ProGrout Flexible Grey"},
    {"sku": "A10848", "name": "Instarmac Ultra ProGrout White"},
    {"sku": "A14219", "name": "Instarmac Ultra ProGrout Brilliant White"},
    {"sku": "A10774", "name": "Instarmac Ultra ProGrout Flexible Jasmine"},
    {"sku": "A10849", "name": "Instarmac Ultra ProGrout Flexible Limestone"},
    {"sku": "A10837", "name": "Instarmac Ultra ProGrout Flexible Charcoal"},
    {"sku": "A10838", "name": "Instarmac ultra ProGrout Flexible Silver Grey"},
    {"sku": "A10776", "name": "Instarmac Ultra ProGrout Flexible Grey"},
    {"sku": "A10779", "name": "Instarmac Ultra ProSealer White"},
    {"sku": "A10780", "name": "Instarmac Ultra ProSealer Jasmine"},
    {"sku": "A10850", "name": "Instarmac Ultra ProSealer Limestone"},
    {"sku": "A10783", "name": "Instarmac Ultra ProSealer Charcoal"},
    {"sku": "A10781", "name": "Instarmac Ultra ProSealer Silver Grey"},
    {"sku": "A10782", "name": "Instarmac Ultra ProSealer Grey"},
    {"sku": "A10772", "name": "Instarmac Ultra ProLevel Fibre"},
    {"sku": "A10851", "name": "Instarmac Ultra ProPrimer"},
    {"sku": "A10852", "name": "Instarmac Ultra Pro ProPrimer"},
    {"sku": "A10959", "name": "Instarmac ProGrout Flowable Limestone"},
    {"sku": "A10960", "name": "Instarmac ProGrout Flowable Silver"},
    {"sku": "A10962", "name": "Instarmac ProGrout Flowable Grey"},
    {"sku": "A10963", "name": "Instarmac ProGrout Flowable Charcoal"},
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
    {"sku": "A10840", "name": "ProBacker"},
    {"sku": "A12144", "name": "Pro Backer Cement Backer Board 600x1200x6mm"},
    {"sku": "A10084", "name": "ProBacker"},
    {"sku": "A12415", "name": "Pro Backer Cement Backer Board 800x1200x12mm"},
    {"sku": "D10419", "name": "MosaicFix"},
]

# ============================================================================
# DATA FROM YOUR SYSTEM (PDF extraction - sample of key products)
# These are products in your database with Supplier Name mappings
# ============================================================================
# Key products from your system that reference Verona supplier names
SYSTEM_PRODUCTS = [
    {"code": "VER-A10084", "supplier_name": "Cement Backer Board 80x120cm", "our_name": "Cement Backer Board 80x120cm"},
    {"code": "VHW5002501", "supplier_name": "Cliveden White Wall Tile 500x250mm", "our_name": "Hampton White 500x250 Matt"},
    {"code": "VHG250500", "supplier_name": "Cliveden Grey Wall Tile 250x500mm", "our_name": "Hampton Grey 250x500 Matt"},
    {"code": "VHW500250", "supplier_name": "Cliveden Concept Decor White Wall Tile", "our_name": "Hampton White 500x250 Decor Matt"},
    {"code": "VHG500250", "supplier_name": "Cliveden Concept Decor Grey Wall Tile", "our_name": "Hampton Grey 500x250 Decor Matt"},
    {"code": "VLG250500", "supplier_name": "Gemstone Grey Wall Tile 250x500mm", "our_name": "Liverpool Grey 250x500 Matt"},
    {"code": "VLG500250", "supplier_name": "Gemstone Geo Grey Wall Tile 500x250", "our_name": "Liverpool Grey 500x250 Matt"},
    {"code": "VL5002501", "supplier_name": "Gemstone Geo Avorio Wall Tile 500x250", "our_name": "Liverpool 500x250 Matt"},
    {"code": "VL500250", "supplier_name": "Gemstone Avorio Wall Tile 500x250mm", "our_name": "Liverpool 500x250 Matt"},
    {"code": "VPW250500", "supplier_name": "Polesden Art Decor White Wall Tile", "our_name": "Polesden White 250x500 Matt"},
    {"code": "VPC500250", "supplier_name": "Polesden Art Decor Cream Wall Tile", "our_name": "Polesden Cream 500x250 Matt"},
    {"code": "VVW100300", "supplier_name": "Metro White Wall Tile 100x300mm", "our_name": "Victoria White 100x300 Gloss"},
    {"code": "VVG1003002", "supplier_name": "Metro Light Grey Wall Tile 100x300mm", "our_name": "Victoria Grey 100x300 Gloss"},
    {"code": "VVG1003001", "supplier_name": "Metro Graphite Wall Tile 100x300mm", "our_name": "Victoria Graphite 100x300 Gloss"},
    {"code": "VVG100300", "supplier_name": "Metro Dark Grey Wall Tile 100x300mm", "our_name": "Victoria Grey 100x300 Gloss"},
    {"code": "VVB1003001", "supplier_name": "Metro Bone Wall Tile 100x300mm", "our_name": "Victoria Bone 100x300 Gloss"},
    {"code": "VVB100300", "supplier_name": "Metro Black Wall Tile 100x300mm", "our_name": "Victoria Black 100x300 Gloss"},
    {"code": "VL597297", "supplier_name": "Bosco Anthracite Wall & Floor Tile", "our_name": "Lucca Anthracite 597x297 Matt"},
    {"code": "VLC597297", "supplier_name": "Bosco Cream Wall & Floor Tile 597x297", "our_name": "Lucca Cream 597x297 Matt"},
    {"code": "VLG597297", "supplier_name": "Bosco Grey Wall & Floor Tile 597x297", "our_name": "Lucca Grey 597x297 Matt"},
    {"code": "VL5972971", "supplier_name": "Bosco Mink Wall & Floor Tile 597x297", "our_name": "Lucca 597x297 Matt"},
    {"code": "VT333550", "supplier_name": "Theodore Gris Décor Wall Tile 333x550", "our_name": "Theodore 333x550 Gloss"},
    {"code": "VT3335501", "supplier_name": "Theodore Gris Wall Tile 333x550mm", "our_name": "Theodore 333x550 Gloss"},
    {"code": "VT3335502", "supplier_name": "Theodore Perla Wall Tile 333x550mm", "our_name": "Theodore 333x550 Gloss"},
    {"code": "VVW300600", "supplier_name": "Vernazza Bianco Wall Tile 300x600mm", "our_name": "Vernazza White 300x600 Matt"},
    {"code": "VV300600", "supplier_name": "Vernazza Décor Wall Tile 300x600mm", "our_name": "Vernazza 300x600 Matt"},
    {"code": "VSO150600", "supplier_name": "Sherwood Oak Glazed Wall & Floor Tile", "our_name": "Sherwood Oak 150x600 Matt"},
    {"code": "VSG150600", "supplier_name": "Sherwood Smoke Grey Wall & Floor Tile", "our_name": "Sherwood Grey 150x600 Matt"},
    {"code": "VKG3006004", "supplier_name": "Anderley Light Grey Wall & Floor Tile", "our_name": "Kensington Grey 300x600 Polished"},
    {"code": "VKG6006003", "supplier_name": "Anderley Light Grey Wall & Floor Tile", "our_name": "Kensington Grey 600x600 Polished"},
    {"code": "VKG3006002", "supplier_name": "Anderley Dark Grey Wall & Floor Tile", "our_name": "Kensington Grey 300x600 Polished"},
    {"code": "VKG6006001", "supplier_name": "Anderley Dark Grey Wall & Floor Tile", "our_name": "Kensington Grey 600x600 Polished"},
    {"code": "VGG75300", "supplier_name": "Gradient Plain Grey Wall Tile 75x300", "our_name": "Gradient Grey 75x300 Gloss"},
    {"code": "VFG1301303", "supplier_name": "Cementum Dark Grey Matt 130x130mm", "our_name": "Ferrara Grey 130x130 Matt"},
    {"code": "VFG1301302", "supplier_name": "Cementum Light Grey Matt Ceramic Tile", "our_name": "Ferrara Grey 130x130 Matt"},
    {"code": "VFB1301302", "supplier_name": "Cementum Black Matt Ceramic 130x130", "our_name": "Ferrara Black 130x130 Matt"},
    {"code": "VP2002001", "supplier_name": "Adorne Pamplona Matt Porcelain 200x200", "our_name": "Padova 200x200 Matt"},
    {"code": "VMB335335", "supplier_name": "Mondrian Navy Blue Patterned Wall & Floor", "our_name": "Mondrian Blue 335x335 Matt"},
    {"code": "VMC335335", "supplier_name": "Mondrian Charcoal Patterned Wall & Floor", "our_name": "Mondrian Charcoal 335x335 Matt"},
    {"code": "VVB335335", "supplier_name": "Vincent Navy Blue Patterned Wall & Floor", "our_name": "Vincent Blue 335x335 Matt"},
    {"code": "VVG335335", "supplier_name": "Vincent Grey Patterned Wall & Floor Tile", "our_name": "Vincent Grey 335x335 Matt"},
    {"code": "VW3006001", "supplier_name": "Waldorf Wall Tile 300x600mm", "our_name": "Waldorf 300x600 Gloss"},
    {"code": "VW3006002", "supplier_name": "Waldorf Décor Wall Tile 300x600mm", "our_name": "Waldorf 300x600 Matt"},
    {"code": "VPG3006001", "supplier_name": "Laurent Grey Wall Tile 300x600mm", "our_name": "Prato Grey 300x600 Gloss"},
    {"code": "VPG3006002", "supplier_name": "Laurent Grey Decor Wall Tile 300x600", "our_name": "Prato Grey 300x600 Matt"},
    {"code": "VPB3006001", "supplier_name": "Laurent Beige Wall Tile 300x600mm", "our_name": "Prato Beige 300x600 Gloss"},
    {"code": "VPB3006002", "supplier_name": "Laurent Beige Decor Wall Tile 300x600", "our_name": "Prato Beige 300x600 Matt"},
    {"code": "VO300600", "supplier_name": "Oscar Wall Tile 300x600mm", "our_name": "Oscar 300x600 Matt"},
    {"code": "VVG600300", "supplier_name": "Vander Grey Wall Tile 600x300mm", "our_name": "Vander Grey 600x300 Matt"},
    {"code": "VL30060011", "supplier_name": "George Arena Wall Tile 300x600mm", "our_name": "Liverpool 300x600 Matt"},
    {"code": "VL30060012", "supplier_name": "George Perla Wall Tile 300x600mm", "our_name": "Liverpool 300x600 Matt"},
    {"code": "VRW1002001", "supplier_name": "Central White Wall Tile 100x200mm", "our_name": "Ravenna White 100x200 Gloss"},
    {"code": "VRW100200", "supplier_name": "Central Matt White Wall Tile 100x200", "our_name": "Ravenna White 100x200 Matt"},
    {"code": "VRG100200", "supplier_name": "Central Light Grey Wall Tile 100x200mm", "our_name": "Ravenna Grey 100x200 Gloss"},
    {"code": "VR100200", "supplier_name": "Central Bone Wall Tile 100x200mm", "our_name": "Ravenna Bone 100x200 Gloss"},
    {"code": "VRB1002001", "supplier_name": "Central Black Wall Tile 100x200mm", "our_name": "Ravenna Black 100x200 Gloss"},
    {"code": "VRB100200", "supplier_name": "Central Black Matt Wall Tile 100x200", "our_name": "Ravenna Black 100x200 Matt"},
    {"code": "VRB1002002", "supplier_name": "Central Midnight Blue Wall Tile 100x200", "our_name": "Ravenna Blue 100x200 Gloss"},
    {"code": "VUS300450", "supplier_name": "Zeta Silver Wall Tile 300x450mm", "our_name": "Urbino Silver 300x450 Gloss"},
    {"code": "VUD300450", "supplier_name": "Zeta Dove Wall Tile 300x450mm", "our_name": "Urbino Dove 300x450 Gloss"},
    {"code": "VDW3006001", "supplier_name": "Derwent White Glazed Porcelain 300x600", "our_name": "Derwent White 300x600"},
    {"code": "VDG3006003", "supplier_name": "Derwent Light Grey Glazed Porcelain 300x600", "our_name": "Derwent Grey 300x600"},
    {"code": "VDG3006002", "supplier_name": "Derwent Dark Grey Glazed Porcelain 300x600", "our_name": "Derwent Grey 300x600"},
    {"code": "VM60012003", "supplier_name": "Hannah Polished Glazed Porcelain W&F", "our_name": "Massa 600x1200 Polished"},
    {"code": "VM60012004", "supplier_name": "Hannah Soft Matt Glazed Porcelain W&F", "our_name": "Massa 600x1200 Matt"},
]

def normalize_name(name):
    """Normalize product name for comparison"""
    if not name:
        return ""
    name = name.lower()
    # Remove size info like 300x600, 100x200mm etc
    name = re.sub(r'\d+x\d+\s*(mm)?', '', name)
    # Remove special characters
    name = re.sub(r'[^\w\s]', '', name)
    # Remove extra spaces
    name = ' '.join(name.split())
    return name.strip()

def extract_key_words(name):
    """Extract key identifying words from product name"""
    if not name:
        return set()
    name = name.lower()
    # Remove common suffixes
    name = re.sub(r'(wall|floor|tile|mosaic|matt|gloss|polished|satin|glazed|porcelain|ceramic)\s*(&|and)?\s*', ' ', name)
    name = re.sub(r'\d+x\d+\s*(mm)?', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    words = set(name.split())
    # Remove very common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
    return words - stop_words

def find_matches():
    """Find matching products between supplier list and system"""
    # Build lookup structures
    supplier_by_normalized = {}
    for p in SUPPLIER_PRODUCTS:
        norm = normalize_name(p['name'])
        if norm not in supplier_by_normalized:
            supplier_by_normalized[norm] = []
        supplier_by_normalized[norm].append(p)
    
    supplier_keywords = {}
    for p in SUPPLIER_PRODUCTS:
        keywords = extract_key_words(p['name'])
        for kw in keywords:
            if kw not in supplier_keywords:
                supplier_keywords[kw] = []
            supplier_keywords[kw].append(p)
    
    matches = []
    unmatched_system = []
    matched_supplier_skus = set()
    
    for sys_prod in SYSTEM_PRODUCTS:
        supplier_name = sys_prod['supplier_name']
        norm_name = normalize_name(supplier_name)
        keywords = extract_key_words(supplier_name)
        
        found = False
        matched_supplier = None
        
        # Try exact normalized match
        if norm_name in supplier_by_normalized:
            matched_supplier = supplier_by_normalized[norm_name][0]
            found = True
        
        # Try keyword matching
        if not found and keywords:
            best_match = None
            best_score = 0
            for sp in SUPPLIER_PRODUCTS:
                sp_keywords = extract_key_words(sp['name'])
                if sp_keywords and keywords:
                    common = keywords & sp_keywords
                    score = len(common) / max(len(keywords), len(sp_keywords))
                    if score > best_score and score > 0.5:
                        best_score = score
                        best_match = sp
            if best_match:
                matched_supplier = best_match
                found = True
        
        if found and matched_supplier:
            matches.append({
                'system_code': sys_prod['code'],
                'system_supplier_name': sys_prod['supplier_name'],
                'system_our_name': sys_prod['our_name'],
                'supplier_sku': matched_supplier['sku'],
                'supplier_name': matched_supplier['name']
            })
            matched_supplier_skus.add(matched_supplier['sku'])
        else:
            unmatched_system.append(sys_prod)
    
    # Find supplier products not in system
    unmatched_supplier = [p for p in SUPPLIER_PRODUCTS if p['sku'] not in matched_supplier_skus]
    
    return matches, unmatched_system, unmatched_supplier

def generate_excel_report():
    """Generate Excel report with color-coded sections"""
    matches, unmatched_system, unmatched_supplier = find_matches()
    
    # Create workbook
    output_file = '/app/frontend/public/Verona-Product-Comparison-Report.xlsx'
    workbook = xlsxwriter.Workbook(output_file)
    
    # Define formats
    title_format = workbook.add_format({
        'bold': True, 'font_size': 16, 'font_color': 'white',
        'bg_color': '#1e3a5f', 'align': 'center', 'valign': 'vcenter'
    })
    header_format = workbook.add_format({
        'bold': True, 'font_size': 11, 'font_color': 'white',
        'bg_color': '#2c5282', 'border': 1, 'text_wrap': True
    })
    match_format = workbook.add_format({
        'bg_color': '#c6efce', 'border': 1  # Light green
    })
    system_only_format = workbook.add_format({
        'bg_color': '#ffc7ce', 'border': 1  # Light red - delete from system
    })
    supplier_only_format = workbook.add_format({
        'bg_color': '#ffeb9c', 'border': 1  # Light orange - add to system
    })
    normal_format = workbook.add_format({'border': 1})
    summary_format = workbook.add_format({
        'bold': True, 'font_size': 12, 'bg_color': '#e2e8f0', 'border': 1
    })
    
    # =========================================================================
    # SUMMARY SHEET
    # =========================================================================
    summary_sheet = workbook.add_worksheet('Summary')
    summary_sheet.set_column('A:A', 50)
    summary_sheet.set_column('B:B', 20)
    
    summary_sheet.merge_range('A1:B1', 'VERONA PRODUCT COMPARISON REPORT', title_format)
    summary_sheet.write('A3', f'Report Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', normal_format)
    
    summary_sheet.write('A5', 'SUMMARY', summary_format)
    summary_sheet.write('B5', 'COUNT', summary_format)
    
    summary_sheet.write('A6', '✅ MATCHED Products (In Both Lists)', match_format)
    summary_sheet.write('B6', len(matches), match_format)
    
    summary_sheet.write('A7', '❌ System Only (DELETE - Not in Supplier List)', system_only_format)
    summary_sheet.write('B7', len(unmatched_system), system_only_format)
    
    summary_sheet.write('A8', '➕ Supplier Only (ADD - Not in Your System)', supplier_only_format)
    summary_sheet.write('B8', len(unmatched_supplier), supplier_only_format)
    
    summary_sheet.write('A10', 'Total in Supplier Pricelist:', normal_format)
    summary_sheet.write('B10', len(SUPPLIER_PRODUCTS), normal_format)
    
    summary_sheet.write('A11', 'Total in Your System:', normal_format)
    summary_sheet.write('B11', len(SYSTEM_PRODUCTS), normal_format)
    
    # Legend
    summary_sheet.write('A14', 'COLOR LEGEND:', summary_format)
    summary_sheet.write('A15', 'GREEN - Matched products (keep in system)', match_format)
    summary_sheet.write('A16', 'RED - System only (consider deleting)', system_only_format)
    summary_sheet.write('A17', 'ORANGE - Supplier only (consider adding)', supplier_only_format)
    
    # =========================================================================
    # MATCHED PRODUCTS SHEET (GREEN)
    # =========================================================================
    match_sheet = workbook.add_worksheet('✅ Matched Products')
    match_sheet.set_column('A:A', 15)
    match_sheet.set_column('B:B', 45)
    match_sheet.set_column('C:C', 40)
    match_sheet.set_column('D:D', 15)
    match_sheet.set_column('E:E', 45)
    
    match_sheet.merge_range('A1:E1', f'MATCHED PRODUCTS ({len(matches)} products)', title_format)
    match_sheet.write('A2', 'Your Code', header_format)
    match_sheet.write('B2', 'Supplier Name (in your system)', header_format)
    match_sheet.write('C2', 'Your Product Name', header_format)
    match_sheet.write('D2', 'Verona SKU', header_format)
    match_sheet.write('E2', 'Verona Product Name', header_format)
    
    for i, m in enumerate(matches, start=3):
        match_sheet.write(f'A{i}', m['system_code'], match_format)
        match_sheet.write(f'B{i}', m['system_supplier_name'], match_format)
        match_sheet.write(f'C{i}', m['system_our_name'], match_format)
        match_sheet.write(f'D{i}', m['supplier_sku'], match_format)
        match_sheet.write(f'E{i}', m['supplier_name'], match_format)
    
    # =========================================================================
    # SYSTEM ONLY SHEET (RED - DELETE)
    # =========================================================================
    system_sheet = workbook.add_worksheet('❌ Delete from System')
    system_sheet.set_column('A:A', 20)
    system_sheet.set_column('B:B', 50)
    system_sheet.set_column('C:C', 50)
    system_sheet.set_column('D:D', 60)
    
    system_sheet.merge_range('A1:D1', f'PRODUCTS TO DELETE ({len(unmatched_system)} products - Not in Verona Pricelist)', title_format)
    system_sheet.write('A2', 'Your Code', header_format)
    system_sheet.write('B2', 'Supplier Name', header_format)
    system_sheet.write('C2', 'Your Product Name', header_format)
    system_sheet.write('D2', 'Action', header_format)
    
    for i, p in enumerate(unmatched_system, start=3):
        system_sheet.write(f'A{i}', p['code'], system_only_format)
        system_sheet.write(f'B{i}', p['supplier_name'], system_only_format)
        system_sheet.write(f'C{i}', p['our_name'], system_only_format)
        system_sheet.write(f'D{i}', 'DELETE - Not in supplier pricelist', system_only_format)
    
    # =========================================================================
    # SUPPLIER ONLY SHEET (ORANGE - ADD)
    # =========================================================================
    supplier_sheet = workbook.add_worksheet('➕ Add to System')
    supplier_sheet.set_column('A:A', 15)
    supplier_sheet.set_column('B:B', 60)
    supplier_sheet.set_column('C:C', 20)
    
    supplier_sheet.merge_range('A1:C1', f'PRODUCTS TO ADD ({len(unmatched_supplier)} products - In Verona but not in your system)', title_format)
    supplier_sheet.write('A2', 'Verona SKU', header_format)
    supplier_sheet.write('B2', 'Verona Product Name', header_format)
    supplier_sheet.write('C2', 'Action', header_format)
    
    for i, p in enumerate(unmatched_supplier, start=3):
        supplier_sheet.write(f'A{i}', p['sku'], supplier_only_format)
        supplier_sheet.write(f'B{i}', p['name'], supplier_only_format)
        supplier_sheet.write(f'C{i}', 'ADD to system', supplier_only_format)
    
    workbook.close()
    
    print(f"Report generated: {output_file}")
    print(f"\nSummary:")
    print(f"  ✅ Matched: {len(matches)} products")
    print(f"  ❌ Delete from system: {len(unmatched_system)} products")
    print(f"  ➕ Add to system: {len(unmatched_supplier)} products")
    
    return output_file

if __name__ == "__main__":
    generate_excel_report()
