// ---- gas sheet suite: the master workbook's GAS CALCS riser 1 (Ellen Street), reproduced ----
// FRONT PAGE: demand/dwelling 40 MJ/hr, table F.24 (steel, 2.75-5 kPa), index length 200 m,
// diversity ON, tolerance blank (x1.1). Dwellings: GF 7, LEVEL 1..15 four each (67 total).

note('--- reference data ---');
ok('diversity(67)', gasDiversity(67), 0.203);
ok('diversity(52)', gasDiversity(52), 0.225);
ok('diversity(16)', gasDiversity(16), 0.447);
ok('diversity(4)',  gasDiversity(4),  0.674);
ok('diversity(1)',  gasDiversity(1),  1);
ok('diversity(200) clamps to row 80', gasDiversity(200), 0.195);
ok('diversity(2.5) floors to 2', gasDiversity(2.5), 0.73);
ok('F.24 @200m DN15', gasCapacity('f24',15,200), 41);
ok('F.24 @200m DN50', gasCapacity('f24',50,200), 1004);
ok('F.24 @200m DN150', gasCapacity('f24',150,200), 18266);
ok('F.12 @4m DN65 nulled (bad workbook cell)', gasCapacity('f12',65,4), null);
ok('F.12 @200m DN100', gasCapacity('f12',100,200), 5569);
ok('untabulated length is null', gasCapacity('f24',15,7), null);

note('--- GAS CALCS column G (adjusted demand) ---');
ok('G5  GF     67 dw', Math.round(gasAdjusted(67,40,true,0)*100)/100, 544.04);
ok('G6  L1     60 dw', Math.round(gasAdjusted(60,40,true,0)*100)/100, 506.4);
ok('G8  L3     52 dw', Math.round(gasAdjusted(52,40,true,0)*100)/100, 468);
ok('G17 L12    16 dw', Math.round(gasAdjusted(16,40,true,0)*100)/100, 286.08);
ok('G20 L15     4 dw', Math.round(gasAdjusted(4,40,true,0)*100)/100, 107.84);
ok('no dwellings -> plant load alone', gasAdjusted(0,40,true,250), 250);
ok('diversity OFF is undiversified', gasAdjusted(10,40,false,0), 400);
ok('plant load is added AFTER diversity', Math.round(gasAdjusted(4,40,true,100)*100)/100, 207.84);

note('--- GAS CALCS column H (pipe size), F.24 @ 200 m ---');
function size(mj){ var p=selectGasPipe(mj*1.1,'f24',200); return p?p.DN:null; }
ok('H5  GF', size(544.04), 50);
ok('H8  L3', size(468), 40);
ok('H17 L12', size(286.08), 32);
ok('H20 L15', size(107.84), 25);
ok('over the table top', selectGasPipe(999999,'f24',200), null);

note('--- second acceptance case: the Ellen Street MAIN PIPE sheet ---');
// 327 dwellings at 70 MJ/hr, diversity ON (0.195), 5880 MJ/hr of plant load, F.12 copper @ 200 m.
// The sheet publishes CI22 = 10343.55 and CV22 = 150.
ok('MAIN PIPE CI22', Math.round(gasAdjusted(327,70,true,5880)*100)/100, 10343.55);
ok('MAIN PIPE CV22', selectGasPipe(10343.55*1.1,'f12',200).DN, 150);

note('--- the drawn sheet: build riser 1 and read the schematic back ---');
state.building={job:{name:'ELLEN ST','number':'22058'},
  levels:['GF','LEVEL 1','LEVEL 2','LEVEL 3','LEVEL 4','LEVEL 5','LEVEL 6','LEVEL 7','LEVEL 8',
          'LEVEL 9','LEVEL 10','LEVEL 11','LEVEL 12','LEVEL 13','LEVEL 14','LEVEL 15'],
  groundIdx:0};
switchService('gas');
var gs=curSvc();
gs.nodes=[]; gs.pipes=[]; state.nextId=1;
Object.assign(supplyGas(), {table:'f24', indexLength:200, demandPerDwelling:40, diversity:true, tolerancePct:''});
var src={id:nid(),type:'source',x:160,y:levelY(0)+56,name:'GAS SUPPLY'};
var riser={id:nid(),type:'riser',x:420,name:'GAS RISER 1',start:0,
  data:state.building.levels.map(function(){return blankLevel();}),rl:blankRl(),gas:blankGas()};
riser.data[0].dwellings=7;
for(var i=1;i<=15;i++) riser.data[i].dwellings=4;
gs.nodes.push(src,riser);
var feedAtt={node:riser.id,level:0};
var q=attachPoint(feedAtt);
gs.pipes.push({id:nid(),pts:[{x:src.x,y:src.y},{x:q.x,y:src.y},{x:q.x,y:q.y}],a:{node:src.id},b:feedAtt});

var res=sizePipes();
var feedPipe=gs.pipes[0];
var fr=res[feedPipe.id]||{};
ok('feed main dwellings', fr.dwellings, 67);
ok('feed main MJ/hr', Math.round(fr.mj*100)/100, 544.04);
ok('feed main size = H5', fr.dn, 50);
ok('feed main carries a capacity', fr.cap, 1004);

var info=riserInfo[riser.id];
var segs=riserSegments(riser, info.feed, info.exports, riserBotIdx(riser), riserTopIdx(riser));
function seg(i){ for(var k=0;k<segs.length;k++) if(segs[k].i===i) return segs[k]; return null; }
ok('segment into L3 dwellings', seg(2).dwellings, 52);
ok('segment into L3 size = H8', seg(2).dn, 40);
ok('segment into L12 dwellings', seg(11).dwellings, 16);
ok('segment into L12 size = H17', seg(11).dn, 32);
ok('segment into L15 dwellings', seg(14).dwellings, 4);
ok('segment into L15 size = H20', seg(14).dn, 25);

note('--- per-riser override beats the sheet default (single riser) ---');
riser.gas.indexLength=20;   // 598.44 MJ/hr needs DN32 over 20 m, DN50 over 200 m
res=sizePipes();
ok('riser override changes the feed size', res[feedPipe.id].dn, 32);
ok('sheet default untouched', supplyGas().indexLength, 200);
riser.gas.indexLength='';
res=sizePipes();
ok('clearing the override restores the sheet value', res[feedPipe.id].dn, 50);
riser.gas.demandPerDwelling=80;
res=sizePipes();
ok('demand/dwelling override', Math.round(res[feedPipe.id].mj*100)/100, Math.round(67*80*0.203*100)/100);
riser.gas.demandPerDwelling='';
riser.gas.diversity='off';
res=sizePipes();
ok('diversity OFF override', res[feedPipe.id].mj, 67*40);
riser.gas.diversity='';
res=sizePipes();
ok('back to the sheet default', Math.round(res[feedPipe.id].mj*100)/100, 544.04);

note('--- diversity is applied once, never added (two risers on one main) ---');
var r2={id:nid(),type:'riser',x:760,name:'GAS RISER 2',start:0,
  data:state.building.levels.map(function(){return blankLevel();}),rl:blankRl(),gas:blankGas()};
r2.data[0].dwellings=7;
for(var j=1;j<=15;j++) r2.data[j].dwellings=4;
gs.nodes.push(r2);
var att2={node:r2.id,level:0}, q2=attachPoint(att2);
gs.pipes.push({id:nid(),pts:[{x:q.x,y:q.y},{x:q2.x,y:q.y},{x:q2.x,y:q2.y}],a:feedAtt,b:att2});
res=sizePipes();
var shared=res[gs.pipes[0].id]||{};
ok('shared main dwellings = 134', shared.dwellings, 134);
// 134 dwellings sits past the 80-row curve, so the factor is the clamped 0.195
ok('shared main MJ/hr (diversified once)', Math.round(shared.mj*100)/100, Math.round(134*40*0.195*100)/100);
note('summing the two risers instead would give '+Math.round(544.04*2)+' MJ/hr — the bug this guards');
ok('shared main is NOT the naive sum', shared.mj < 544.04*2, true);
ok('shared main size (1045.2 x 1.1 -> DN65)', shared.dn, 65);

note('--- plant load on a level ---');
riser.data[15].mj=2520;
res=sizePipes();
ok('plant load reaches the feed main', Math.round((res[feedPipe.id].mj)*100)/100, Math.round((1045.2+2520)*100)/100);
riser.data[15].mj=0;

note('--- the water sheets are unchanged ---');
switchService('cw');
ok('cold water demand curve', Math.round(flowFromDwellings(67)*1000)/1000, Math.round((0.03*67+0.4554*Math.sqrt(67))*1000)/1000);
ok('cold water pipe pick at 2.0 L/s copper 2.5 m/s', selectPipe(2.0,'copper_type_b',2.5).DN, 40);
ok('hot water table lookup', hwFlowFromDwellings(20), 1.50);
ok('cw sheet still sizes on velocity', SERVICE_DEF.cw.kind, 'water');
ok('gas sheet is flagged gas', SERVICE_DEF.gas.kind, 'gas');

note('--- save / load round trip ---');
switchService('gas');
var saved=JSON.parse(JSON.stringify({version:6,building:state.building,settings:state.settings,
  activeService:'gas',services:state.services,nextId:state.nextId}));
loadState(saved);
ok('v6 reloads on the gas sheet', state.activeService, 'gas');
ok('v6 keeps the sheet table', supplyGas().table, 'f24');
ok('v6 keeps the plant-load column', typeof curSvc().nodes.filter(function(n){return n.type==='riser';})[0].data[0].mj, 'number');
var reres=sizePipes();
var refeed=curSvc().pipes[0];
ok('v6 sizes identically after reload', reres[refeed.id].dn, 65);

// a v5 file has no gas service at all
var v5={version:5,building:state.building,settings:state.settings,activeService:'cw',
  services:{cw:{network:{material:'copper_type_b',maxVelocity:2.5},nodes:[],pipes:[]},
            hw:{network:{material:'copper_type_b',maxVelocity:1.2},nodes:[],pipes:[]}},nextId:1};
loadState(JSON.parse(JSON.stringify(v5)));
ok('v5 file gains a gas sheet', !!state.services.gas, true);
ok('v5 gas sheet gets the defaults', state.services.gas.network.gas.indexLength, 200);
ok('v5 file lands on cold water', state.activeService, 'cw');
