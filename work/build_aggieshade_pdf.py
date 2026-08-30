from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Flowable, Preformatted)
from pathlib import Path

OUT = Path('/Users/daeyeon/Documents/ChatGPT/AggieShade/output/pdf/AggieShade_Development_Plan.pdf')
OUT.parent.mkdir(parents=True, exist_ok=True)

MAROON = colors.HexColor('#500000'); DARK = colors.HexColor('#182028'); GREEN = colors.HexColor('#2E6B4F')
GOLD = colors.HexColor('#D6A84B'); PALE = colors.HexColor('#F4F1EB'); LIGHT = colors.HexColor('#E7ECE8')
MID = colors.HexColor('#66736C'); WHITE = colors.white

class Architecture(Flowable):
    def __init__(self, width=480, height=260): super().__init__(); self.width=width; self.height=height
    def draw(self):
        c=self.canv
        boxes=[
            (10,190,105,46,'TAMU GIS','trees / buildings'),(130,190,105,46,'OpenStreetMap','pedestrian paths'),
            (255,190,105,46,'Time + place','date / solar position'),(375,190,95,46,'Mobile app','React Native'),
            (35,105,135,50,'Geo database','PostgreSQL + PostGIS'),(205,105,130,50,'Shade engine','projected shadows'),
            (365,105,105,50,'REST API','FastAPI'),(105,20,130,50,'Weighted graph','shade per edge'),
            (285,20,130,50,'Route engine','A* / Dijkstra')]
        def arrow(x1,y1,x2,y2):
            c.setStrokeColor(MID); c.setLineWidth(1.4); c.line(x1,y1,x2,y2)
            import math
            a=math.atan2(y2-y1,x2-x1)
            for d in (-0.45,0.45): c.line(x2,y2,x2-7*math.cos(a+d),y2-7*math.sin(a+d))
        arrow(62,190,80,155); arrow(182,190,120,155); arrow(307,190,270,155)
        arrow(170,130,205,130); arrow(335,130,365,130); arrow(103,105,160,70); arrow(270,105,215,70)
        arrow(235,45,285,45); arrow(417,105,360,70); arrow(415,190,417,155)
        for x,y,w,h,t,s in boxes:
            c.setFillColor(WHITE); c.setStrokeColor(MAROON); c.setLineWidth(1.4); c.roundRect(x,y,w,h,7,fill=1,stroke=1)
            c.setFillColor(DARK); c.setFont('Helvetica-Bold',9); c.drawCentredString(x+w/2,y+h-17,t)
            c.setFillColor(MID); c.setFont('Helvetica',7.5); c.drawCentredString(x+w/2,y+11,s)

def footer(c, doc):
    c.saveState(); w,h=letter
    c.setStrokeColor(colors.HexColor('#D6DDD8')); c.line(0.72*inch,0.52*inch,w-0.72*inch,0.52*inch)
    c.setFillColor(MID); c.setFont('Helvetica',7.5); c.drawString(0.72*inch,0.34*inch,'AGGIESHADE  |  DEVELOPMENT PLAN')
    c.drawRightString(w-0.72*inch,0.34*inch,str(doc.page)); c.restoreState()

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleX',fontName='Helvetica-Bold',fontSize=33,leading=36,textColor=WHITE,spaceAfter=12))
styles.add(ParagraphStyle(name='SubX',fontName='Helvetica',fontSize=13,leading=19,textColor=colors.HexColor('#F3E8D7')))
styles.add(ParagraphStyle(name='H1X',fontName='Helvetica-Bold',fontSize=22,leading=26,textColor=MAROON,spaceBefore=3,spaceAfter=9))
styles.add(ParagraphStyle(name='H2X',fontName='Helvetica-Bold',fontSize=12,leading=15,textColor=GREEN,spaceBefore=10,spaceAfter=4))
styles.add(ParagraphStyle(name='BodyX',fontName='Helvetica',fontSize=9.2,leading=13.2,textColor=DARK,spaceAfter=6))
styles.add(ParagraphStyle(name='SmallX',fontName='Helvetica',fontSize=7.8,leading=10.5,textColor=DARK))
styles.add(ParagraphStyle(name='SmallWhite',fontName='Helvetica-Bold',fontSize=7.8,leading=10.5,textColor=WHITE))
styles.add(ParagraphStyle(name='CallX',fontName='Helvetica-Bold',fontSize=11,leading=16,textColor=MAROON,alignment=TA_CENTER))
styles.add(ParagraphStyle(name='CodeX',fontName='Courier',fontSize=7.5,leading=10,textColor=DARK,leftIndent=8))

TABLE_HEADERS = {'Layer', 'Recommendation', 'Role', 'Week', 'Outcome', 'Exit criterion', 'Decision', 'Recommendation / rationale'}
def P(t, style='BodyX'):
    if style == 'SmallX' and str(t) in TABLE_HEADERS:
        style = 'SmallWhite'
    return Paragraph(t, styles[style])
def section(title,kicker=None):
    out=[]
    if kicker: out.append(P(kicker.upper(),'SmallX'))
    out += [P(title,'H1X'),HRFlowable(width='100%',thickness=2,color=GOLD,spaceAfter=11)]
    return out
def card(title,text):
    return Table([[P(title,'H2X')],[P(text,'BodyX')]],colWidths=[2.25*inch],style=TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),0.8,colors.HexColor('#D9D3C8')),
        ('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),11),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
def bullets(items): return [P('• '+x) for x in items]

story=[]
# cover
story.append(Table([['']],colWidths=[7.06*inch],rowHeights=[1.1*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),MAROON)])))
story += [Spacer(1,0.65*inch),P('AggieShade','TitleX'),P('Shade-aware pedestrian navigation for the Texas A&M campus','SubX'),Spacer(1,0.35*inch)]
# title must sit on dark block
cover=Table([[P('AGGIESHADE','TitleX')],[P('Development Plan & Technical Proposal','SubX')]],colWidths=[7.06*inch],rowHeights=[0.65*inch,0.42*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),MAROON),('LEFTPADDING',(0,0),(-1,-1),30),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
story=[cover,Spacer(1,0.5*inch),P('A campus routing system that helps pedestrians trade a small amount of travel time for substantially less direct sun exposure.','H1X'),Spacer(1,0.15*inch),Table([[card('Core promise','Enter two campus locations. Compare the fastest route with a time-aware, more shaded alternative.'),card('Technical thesis','Combine pedestrian graph routing, public GIS, solar geometry, and computational geometry - no ML required for the MVP.'),card('Delivery target','A demonstrable v1.0 in 10-12 weeks, with a usable conventional router by the Week 5 checkpoint.')]],colWidths=[2.3*inch]*3,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)])),Spacer(1,0.7*inch),P('Prepared as a student-project technical proposal  |  August 2026','SmallX'),PageBreak()]

story += section('1. Project overview & MVP','Product definition')
story += [P('<b>Problem.</b> College Station heat makes short campus walks uncomfortable, yet conventional navigation optimizes mainly for distance or time. AggieShade makes sun exposure a first-class route cost.'),
P('<b>MVP.</b> A user selects an origin and destination, optionally uses current location, chooses a preference from Fastest to Most Shade, and receives at least two comparable routes with ETA, distance, and estimated percent shaded.'),
Table([[card('Fastest','8 min  |  0.42 mi<br/>31% shaded'),card('Balanced','9 min  |  0.45 mi<br/>56% shaded'),card('Shadiest','10 min  |  0.48 mi<br/>72% shaded<br/><b>+2 min</b>')]],colWidths=[2.3*inch]*3,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')])),
P('Success means the app can explain the tradeoff clearly: “two extra minutes buys 41 percentage points more shade.” Accounts, reviews, social features, AI, live weather, and crowdsourcing remain outside the initial scope.','BodyX'),
P('Key product metrics','H2X'),*bullets(['Route correctness: valid, connected, walkable paths between major campus destinations.','Shade usefulness: predicted shaded portions broadly match field observations at selected test times.','Decision clarity: users can compare time, distance, and shade without interpreting technical data.','Performance: route response feels interactive; expensive shadow work is cached or precomputed.']),PageBreak()]

story += section('2. Recommended technology stack','Implementation platform')
data=[['Layer','Recommendation','Role'],['Mobile','React Native + Expo','One TypeScript codebase; GPS, search, and route map'],['Map','MapLibre (or Mapbox)','Campus basemap, polylines, shade overlays'],['API','Python + FastAPI','Routing requests, validation, service orchestration'],['Geospatial','GeoPandas, Shapely, PyProj','Projection, buffering, intersection, shadow polygons'],['Graph','NetworkX initially','A*/Dijkstra, graph attributes, rapid iteration'],['Storage','PostgreSQL + PostGIS','Spatial layers, graph metadata, cached edge scores'],['Solar','pvlib or Astral','Solar altitude and azimuth by place and time'],['Data jobs','Python scripts / scheduled workers','Download, normalize, build graph, precompute shade']]
story += [Table([[P(str(x),'SmallX') for x in r] for r in data],colWidths=[1.05*inch,1.75*inch,4.1*inch],repeatRows=1,style=TableStyle([('BACKGROUND',(0,0),(-1,0),MAROON),('TEXTCOLOR',(0,0),(-1,0),WHITE),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#CBD3CE')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,PALE]),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])),
P('Why this stack','H2X'),P('The mobile layer stays productive and cross-platform while Python provides a mature geospatial toolchain. PostGIS becomes the durable source of spatial truth. NetworkX is appropriate for a campus-scale prototype; a dedicated routing service can replace it only if performance evidence demands that change.'),PageBreak()]

story += section('3. Data foundation & pedestrian graph','Campus representation')
story += [P('TAMU public ArcGIS services are the project’s main technical advantage. Relevant layers described in the source plan include university buildings, trees, sidewalks, steps, ramps/curb cuts, campus driveways, and roads. Tree records include location, species, height, canopy spread, health, and status; buildings provide footprints and floor counts.'),
P('Data-source strategy','H2X'),*bullets(['Use OpenStreetMap pedestrian ways as the initial routable centerline graph.','Overlay official TAMU tree and building geometry for shade; use sidewalk and accessibility layers for validation and later graph refinement.','Record source date, layer version, units, coordinate reference system, and quality flags during ingestion.','Project all geometry into a local metric CRS before measuring distance, buffering, or casting shadows.']),
P('Graph design','H2X'),P('Intersections, entrances, and path endpoints become nodes. Walkable segments become directed edges. Each edge stores geometry and routing attributes such as length, travel time, slope/accessibility when available, surface, data quality, and a time-indexed shade score.'),
Preformatted("node: id, lat, lon, type\nedge: from, to, geometry, length_m, walk_time_s,\n      shade_ratio[time_bucket], exposure_m, accessibility",styles['CodeX']),
P('Snap user-selected buildings to verified entrances or nearby walkable nodes - not merely to the building centroid. Validate topology for disconnected components, accidental road crossings, duplicate edges, stairs, and restricted areas.'),PageBreak()]

story += section('4. Solar and shade modeling','Computational geometry')
story += [P('At request time, the shade engine computes solar altitude and azimuth for College Station at the selected date and time. For an object height <i>h</i> and solar altitude <i>alpha</i>, an initial shadow-length approximation is:'),
Table([[P('<b>L = h / tan(alpha)</b>','CallX')]],colWidths=[6.8*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),1,GOLD),('TOPPADDING',(0,0),(-1,-1),15),('BOTTOMPADDING',(0,0),(-1,-1),15)])),
P('The shadow extends opposite the solar azimuth. When the sun is below the horizon, daylight routing should treat the route as non-sun-exposed rather than generating unbounded shadows.'),
Table([[card('Trees','Approximate each canopy as a circle or ellipse. Radius starts at canopy spread / 2. Translate/project the canopy opposite the sun using tree height, then optionally apply a transmissivity factor for imperfect foliage.'),card('Buildings','Extrude/project the footprint opposite the sun. When exact elevation is missing, estimate height as floors x 3.5 m and mark the estimate with lower confidence.'),card('Combined shade','Union tree and building shadow polygons for the selected time bucket. Keep provenance so field tests can distinguish building error from canopy error.')]],colWidths=[2.3*inch]*3,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')])),
P('Practical accuracy controls','H2X'),*bullets(['Use 10- or 15-minute time buckets and cache results; interpolate only if testing shows value.','Clip implausibly long shadows near sunrise/sunset and surface low-confidence predictions.','Account for tree health/status and future seasonal canopy factors; avoid claiming physical ray-tracing accuracy.','Create a small ground-truth set: photographed or observed shaded/unshaded segments at multiple times.']),PageBreak()]

story += section('5. Edge shade scoring & routing','Core algorithm')
story += [P('Sample points along each edge every 2-3 meters, or compute the exact geometric intersection length. The baseline shade ratio is the shaded length divided by total edge length:'),
Table([[P('<b>shade(e,t) = shaded_length(e,t) / length(e)</b><br/><b>exposure(e,t) = length(e) x [1 - shade(e,t)]</b>','CallX')]],colWidths=[6.8*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),1,GREEN),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14)])),
P('A simple user-controlled objective is:'),Table([[P('<b>w(e,t) = distance(e) + lambda x exposure(e,t)</b>','CallX')]],colWidths=[6.8*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),1,GOLD),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14)])),
P('Set lambda = 0 for fastest, about 1 for balanced, and a higher calibrated value (for example 3-5) for shadiest. Dijkstra works directly. For A*, use an admissible lower-bound heuristic such as straight-line distance, since the exposure penalty is nonnegative.'),
P('Route-level reporting','H2X'),*bullets(['Distance = sum of edge lengths; ETA = sum of walking times.','Shade percent = total shaded length / total route length - length-weighted, not an average of edge percentages.','Return distinct alternatives. If the “shadiest” path is effectively identical, do not present a fake choice.','Constrain detours (for example, no more than 25-35% beyond fastest) so maximum shade stays useful.']),
P('Later refinements can include UV-weighted exposure, temperature, cloud cover, accessibility, construction closures, and multi-objective Pareto routing.'),PageBreak()]

story += section('6. System architecture','Data flow')
story += [Architecture(),Spacer(1,8),P('The offline pipeline ingests and normalizes spatial sources, builds the walk graph, and prepares time-bucketed shadow/edge data. The online API snaps endpoints, selects the relevant time bucket, applies the user’s lambda, runs A*, and returns route geometry plus comparison metrics to the mobile client.'),
P('API sketch','H2X'),Preformatted("POST /routes\n{ origin, destination, departure_time, shade_preference, accessibility? }\n\n-> fastest_route, recommended_route, alternatives[]\n-> each: geometry, distance_m, duration_s, shade_ratio, confidence",styles['CodeX']),PageBreak()]

story += section('7. UI concepts','Make the tradeoff visible')
ui1=Preformatted("AGGIESHADE\nFrom   Current location\nTo     Zachry Engineering\n\nFastest ----o-------- Most shade\n\n[ Find route ]",styles['CodeX'])
ui2=Preformatted("EVANS -> ZACHRY\n\n  route map + shade overlay\n\nRecommended   10 min | 72% shade\nFastest        8 min | 31% shade\n\n+2 min for +41 pts shade",styles['CodeX'])
story += [Table([[card('Search & preference','Two location fields, current-location shortcut, departure time (“leave now” by default), and one plain-language preference control.'),card('Map & comparison','Emphasize one recommended route while keeping fastest visible. Use distinct line styles/colors and a clear legend; do not rely on color alone.'),card('During navigation','Show next instruction, remaining time, off-route recovery, and a compact shade estimate. Avoid distracting live geometry details.')]],colWidths=[2.3*inch]*3,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')])),Spacer(1,12),Table([[ui1,ui2]],colWidths=[3.35*inch,3.35*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),0.7,colors.HexColor('#D9D3C8')),('INNERGRID',(0,0),(-1,-1),0.7,colors.HexColor('#D9D3C8')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),16),('TOPPADDING',(0,0),(-1,-1),16),('BOTTOMPADDING',(0,0),(-1,-1),16)])),
P('Accessibility and trust','H2X'),P('Use readable contrast, scalable text, explicit units, and accessible route filters when data permits. Label estimates as estimates, include the departure time used, and provide a small “Why this route?” explanation tied to time and shade.'),PageBreak()]

story += section('8. Ten-to-twelve-week roadmap','Execution plan')
road=[['Week','Outcome','Exit criterion'],['1','Requirements, user flows, repository','MVP scope and acceptance tests agreed'],['2','Mobile map, permissions, GPS','Campus map opens; current location works'],['3','Building/place search','Major destinations resolve to map points'],['4','Pedestrian graph pipeline','Connected campus graph persisted'],['5','Conventional A*/Dijkstra routing','Zachry-to-Evans route renders end-to-end'],['6','TAMU GIS ingestion','Trees/buildings normalized and queryable'],['7','Solar-position service','Altitude/azimuth verified for test times'],['8','Tree shadow model','Canopy shadows render for a time bucket'],['9','Building shadow model','Footprint shadows render; heights flagged'],['10','Edge scores + shade routing','Fastest/balanced/shadiest compare correctly'],['11','UX polish + navigation','Metrics, errors, rerouting, accessibility QA'],['12','Field validation + deployment','Campus test report and demo release']]
story += [Table([[P(str(x),'SmallX') for x in r] for r in road],colWidths=[0.55*inch,2.35*inch,3.95*inch],repeatRows=1,style=TableStyle([('BACKGROUND',(0,0),(-1,0),MAROON),('TEXTCOLOR',(0,0),(-1,0),WHITE),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#CBD3CE')),('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,PALE]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)])),
P('<b>Week 5 is the critical checkpoint:</b> the product must already route between two campus buildings. Shade features improve a working navigator; they do not postpone it.'),PageBreak()]

story += section('9. Version milestones & codebase','Build in generations')
story += [Table([[card('v0.1 - Navigator','Campus map, GPS, destination search, ordinary walking route, baseline deployment.'),card('v0.5 - Shade prototype','Imported GIS, static or representative-time shade, edge scoring, shade-aware route.'),card('v1.0 - Dynamic experience','Date/time solar position, dynamic tree/building shadows, route alternatives, shade percentage, field-tested calibration.')]],colWidths=[2.3*inch]*3,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')])),Spacer(1,12),P('Recommended repository structure','H2X'),
Preformatted("AggieShade/\n  mobile/        components/ screens/ maps/ api/\n  backend/\n    routing/     graph.py  astar.py  weights.py\n    shade/       solar.py  trees.py  buildings.py  shadows.py\n    gis/         tamu.py   osm.py\n    models/      request and persistence models\n  scripts/       download_tamu_gis.py  build_graph.py  calculate_shade.py\n  tests/         routing/ geometry/ api/ field_cases/\n  docs/          data dictionary, ADRs, validation notes",styles['CodeX']),
P('Keep ingestion, geometry, routing, and client concerns separate. Store configuration - CRS, floor-height assumption, sampling distance, time-bucket size, and lambda presets - outside algorithm code and document changes in lightweight architecture decision records.'),PageBreak()]

story += section('10. Key decisions, risks & next action','Proposal summary')
dec=[['Decision','Recommendation / rationale'],['Routing base','Start with OSM pedestrian centerlines; overlay and validate against TAMU layers. Avoid deriving perfect centerlines from polygons in the first release.'],['Shade technique','Use computational geometry, not ML. It is explainable, testable, and supported by existing height/canopy/footprint data.'],['Time model','Use cached 10-15 minute buckets before attempting continuous real-time recomputation.'],['Building height','Estimate from floor count only when necessary; carry a confidence flag.'],['Optimization','Use distance plus lambda-weighted sun exposure, with a detour cap and distinct route alternatives.'],['Validation','Field-test selected corridors across morning, midday, and afternoon; measure both route validity and shade agreement.']]
story += [Table([[P(str(x),'SmallX') for x in r] for r in dec],colWidths=[1.25*inch,5.6*inch],repeatRows=1,style=TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('TEXTCOLOR',(0,0),(-1,0),WHITE),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#CBD3CE')),('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,PALE]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])),
P('Primary risks','H2X'),*bullets(['Data freshness or licensing/terms: capture metadata and confirm permitted production use.','Topology errors: automated connectivity tests plus field verification of high-traffic corridors.','Shade uncertainty: confidence indicators, calibrated assumptions, and modest product claims.','Battery/latency: precompute, cache, simplify geometries, and avoid unnecessary client-side spatial work.']),
Table([[P('<b>First coding milestone</b><br/>Launch a React Native campus map, select two TAMU buildings, request an ordinary walking route from FastAPI, and draw the returned path. Complete this vertical slice before building the shade engine.','CallX')]],colWidths=[6.8*inch],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F1E3C5')),('BOX',(0,0),(-1,-1),1.2,GOLD),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14)])),Spacer(1,8),P('Source note: This proposal is based on the complete referenced AggieShade planning conversation. Before implementation, verify current TAMU ArcGIS layer URLs, schemas, update dates, and usage terms; verify current OpenStreetMap coverage and map-provider licensing.','SmallX')]

doc=SimpleDocTemplate(str(OUT),pagesize=letter,rightMargin=0.72*inch,leftMargin=0.72*inch,topMargin=0.65*inch,bottomMargin=0.68*inch,title='AggieShade Development Plan',author='OpenAI Codex')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
