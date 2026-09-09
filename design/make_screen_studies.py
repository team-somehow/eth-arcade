from pathlib import Path
from html import escape
p=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="590" viewBox="0 0 1600 590"><rect width="1600" height="590" fill="#eee9dd"/>']
def text(x,y,s,size=18,color='#eee9dd',weight='normal'):
 p.append(f'<text x="{x}" y="{y}" font-family="monospace" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(s)}</text>')
def rect(x,y,w,h,c,r=0):p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{c}"/>')
text(40,55,'TICK / SCREEN STUDIES',30,'#182a30','bold')
text(40,88,'480 × 320 native layouts · proposed UI · illustrative data',18,'#526261')
for i,title in enumerate(['01 / PICK A CARTRIDGE','02 / PLAY NERVE','03 / VERIFY THE PAYMENT']):
 x=40+i*520
 text(x,137,title,17,'#182a30','bold')
 p.append(f'<g transform="translate({x} 160)">')
 rect(0,0,480,320,'#10252c');rect(0,0,480,30,'#213b40')
 text(16,22,'TICK' if i==0 else 'NERVE',18,weight='bold');text(330,22,'PRACTICE' if i<2 else 'TESTNET',16,'#a4d8b8')
 if i==0:
  text(24,67,'THE MARKET IS YOUR ARCADE.',18,'#a4d8b8')
  rect(24,86,432,154,'#29474a',8)
  rect(47,164,120,9,'#ecc167');rect(98,130,20,25,'#a4d8b8');rect(93,117,30,19,'#eee9dd');rect(96,155,7,10,'#a4d8b8');rect(113,155,7,10,'#a4d8b8')
  text(196,135,'NERVE',34,weight='bold');text(196,169,'Hold your balance.',17);text(196,204,'30 SECOND ROUND',16,'#ecc167')
  text(24,270,'< TURN TO CHOOSE >       01 / 03',18)
 elif i==1:
  text(20,65,'SCORE 0240',23,'#a4d8b8','bold');text(356,65,'18s',30,'#ecc167','bold')
  for bx,by in [(25,199),(67,225),(113,202),(334,216),(384,198),(432,236)]:rect(bx,by,25,25,'#29474a')
  rect(66,178,348,8,'#ecc167');rect(230,186,20,51,'#597776')
  rect(227,138,25,28,'#a4d8b8');rect(223,120,31,23,'#eee9dd');rect(247,126,5,5,'#10252c');rect(219,149,8,7,'#a4d8b8');rect(252,143,13,7,'#a4d8b8');rect(230,166,7,12,'#a4d8b8');rect(246,166,7,12,'#a4d8b8')
  text(70,101,'~',30,'#a4d8b8');text(366,129,'~',30,'#a4d8b8');text(24,268,'INTENSITY 03       FEED: LIVE',17,'#a4d8b8')
 else:
  text(24,72,'PAYMENT CONFIRMED',27,'#a4d8b8','bold')
  text(24,104,'Round access receipt',18)
  rect(24,123,432,102,'#29474a',5)
  text(40,153,'SERVICE',16,'#a4d8b8');text(40,183,'NERVE / 1 ROUND',24,weight='bold');text(40,208,'Paid amount + asset shown here',16)
  text(24,254,'Open verified transaction on phone',17)
  text(24,274,'Receipt layout / no transaction yet',16,'#ecc167')
 rect(0,284,480,36,'#213b40')
 text(16,308,['B BACK                 A PLAY','B LEAN LEFT     A LEAN RIGHT','B HOME            A RECEIPT'][i],18)
 p.append('</g>')
text(40,529,'Cream shell / charcoal UI / mint feedback / amber attention',18,'#526261')
text(40,558,'Concept screens, not running firmware. Confirmed state is illustrative; real receipts require backend verification.',16,'#526261')
p.append('</svg>')
Path(__file__).with_name('screen-studies.svg').write_text(''.join(p))
