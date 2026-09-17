// ---- the HW plant on the gas sheet: a LOAD there, a source on the hot-water sheet.

note('--- set up a building with a gas-fired roof plant ---');
state.building={job:{name:'PLANT',number:'66666'},
  levels:['GROUND','LEVEL 1','LEVEL 2','LEVEL 3'], groundIdx:0};
switchService('cw');
var cw=curSvc(); cw.nodes=[]; cw.pipes=[]; state.nextId=1;
var csrc={id:nid(),type:'source',x:160,y:levelY(0)+56,name:'MAINS SUPPLY'};
var cr={id:nid(),type:'riser',x:420,name:'CW RISER 1',start:0,
  data:state.building.levels.map(function(){return blankLevel();}),rl:blankRl()};
for(var i=0;i<4;i++) cr.data[i].dwellings=5;   // 20 dwellings
cw.nodes.push(csrc,cr);
var ca={node:cr.id,level:0}, cq=attachPoint(ca);
cw.pipes.push({id:nid(),pts:[{x:csrc.x,y:csrc.y},{x:cq.x,y:csrc.y},{x:cq.x,y:cq.y}],a:{node:csrc.id},b:ca});

switchService('hw');                 // auto-builds the HW sheet with a roof plant
var plant=curSvc().nodes.filter(function(n){return n.type==='plant';})[0];
ok('hot-water sheet has a plant', !!plant, true);
plant.plantType='gas_central'; plant.gasLoad=2200;
ok('plant is still a SOURCE on the hot-water sheet', sizePipes()[curSvc().pipes[0].id].unsized, false);
ok('hot water still sizes in L/s', sizePipes()[curSvc().pipes[0].id].flow > 0, true);

note('--- the gas sheet picks it up, in the SAME position ---');
var hwx=plant.x, hwy=plant.y;
switchService('gas');
var gs=curSvc();
var gplant=gs.nodes.filter(function(n){return n.type==='plant';})[0];
ok('gas sheet got the plant', !!gplant, true);
ok('same x as the hot-water sheet', gplant.x, hwx);
ok('same y as the hot-water sheet', gplant.y, hwy);
ok('with its load', gplant.gasLoad, 2200);
ok('and its configuration', gplant.plantType, 'gas_central');
ok('linked back to the hot-water node', gplant.linkedTo, plant.id);
ok('it arrives unconnected: the gas run is for the designer to draw',
   gs.pipes.filter(function(p){
     return (p.a&&p.a.node===gplant.id)||(p.b&&p.b.node===gplant.id); }).length, 0);

note('--- draw the gas main into it, the way a user would ---');
var riser=allRisers()[0];
var topAtt={node:riser.id,level:riserTopIdx(riser)}, tq=attachPoint(topAtt);
gs.pipes.push({id:nid(),pts:dedupe([{x:gplant.x,y:gplant.y+30},{x:gplant.x,y:tq.y},{x:tq.x,y:tq.y}]),
  a:{node:gplant.id}, b:topAtt});

note('--- on gas the plant is a LOAD, so the run into it is sized and not a phantom source ---');
var res=sizePipes();
var feedPipe=null, plantPipe=null;
gs.pipes.forEach(function(p){
  if((p.a&&p.a.node===gplant.id)||(p.b&&p.b.node===gplant.id)) plantPipe=p;
  else if(p.a&&getNode(p.a.node)&&getNode(p.a.node).type==='source') feedPipe=p;
});
ok('the plant run is sized', res[plantPipe.id].unsized, false);
ok('the plant run carries exactly the plant load', res[plantPipe.id].mj, 2200);
ok('it carries no dwellings', res[plantPipe.id].dwellings, 0);

var g=resolveGas(riser);
var dwellingsMj = 20*g.demandPerDwelling*gasDiversity(20);
ok('the incoming main carries dwellings + plant',
   Math.round(res[feedPipe.id].mj*100)/100, Math.round((dwellingsMj+2200)*100)/100);
note('plant is added AFTER diversity - a firm load is never discounted');

note('--- the riser between the supply and the plant carries the plant load ---');
var info=riserInfo[riser.id];
var segs=riserSegments(riser, info.feed, info.exports, riserBotIdx(riser), riserTopIdx(riser));
ok('top segment carries the plant', segs[segs.length-1].mj >= 2200, true);

note('--- changing the load resizes the network ---');
var before=res[feedPipe.id].mj;
gplant.gasLoad=8000;
res=sizePipes();
ok('bigger plant, bigger main', res[feedPipe.id].mj > before, true);
ok('the plant run followed', res[plantPipe.id].mj, 8000);
gplant.gasLoad=2200;

note('--- the graphic shows the load ---');
render();
var svg=document.getElementById('board').textContent;
ok('plant box prints its MJ/hr', svg.indexOf('2,200 MJ/hr')>=0, true);
ok('plant box keeps its configuration kicker', svg.indexOf('GAS · CENTRAL')>=0, true);

note('--- the panel treats it as a load and warns about electric plant ---');
selectNode_(gplant.id);
var pt=document.getElementById('p-body').textContent;
ok('panel kicker says Gas Plant', document.getElementById('p-kicker').textContent, 'Gas Plant');
ok('panel calls it a load', pt.indexOf('is a load')>=0, true);
ok('panel shows what the feed carries', pt.indexOf('Feed carries')>=0, true);
ok('no water pressure block on the gas sheet', pt.indexOf('pump duty'), -1);
var psel=document.querySelector('#ptype');
psel.value='elec_central'; psel.dispatchEvent(new Event('change',{bubbles:true}));
ok('electric plant is flagged', document.getElementById('p-body').textContent.indexOf('draws no gas')>=0, true);
psel=document.querySelector('#ptype'); psel.value='gas_central';
psel.dispatchEvent(new Event('change',{bubbles:true}));
ok('back to gas clears the warning', document.getElementById('p-body').textContent.indexOf('draws no gas'), -1);

note('--- typing a load does not lose focus ---');
var fld=document.querySelector('#pgas');
fld.focus();
fld.value='3'; fld.dispatchEvent(new Event('input',{bubbles:true}));
ok('still focused after the 1st character', document.activeElement===fld, true);
fld.value='3000'; fld.dispatchEvent(new Event('input',{bubbles:true}));
ok('still focused later', document.activeElement===fld, true);
ok('the model took the whole number', gplant.gasLoad, 3000);
ok('and the drawing resized', sizePipes()[plantPipe.id].mj, 3000);

note('--- an electric plant contributes nothing on gas ---');
gplant.plantType='elec_central'; gplant.gasLoad=0;
res=sizePipes();
ok('no load from an electric plant', res[plantPipe.id].unsized, true);
ok('the main drops back to dwellings alone',
   Math.round(res[feedPipe.id].mj*100)/100, Math.round(dwellingsMj*100)/100);

note('--- and the hot-water sheet is untouched by all of it ---');
switchService('hw');
ok('hw plant still a source', sizePipes()[curSvc().pipes[0].id].unsized, false);
ok('hw box has no MJ/hr line', (function(){ render();
  return document.getElementById('board').textContent.indexOf('MJ/hr'); })(), -1);

note('--- adding a plant by hand on each sheet ---');
switchService('gas');
document.querySelector('[data-add="plant"]').click();
ok('gas plant button is labelled for the sheet',
   document.querySelector('[data-add="plant"]').textContent.indexOf('Gas Plant')>=0, true);
var added=curSvc().nodes.filter(function(n){return n.type==='plant';}).pop();
ok('named for the gas sheet', added.name, 'GAS PLANT');
ok('starts with no load', added.gasLoad, 0);
ok('an unconnected plant does not break sizing', typeof sizePipes(), 'object');
deleteSelected();
switchService('hw');
ok('hot-water button label restored',
   document.querySelector('[data-add="plant"]').textContent.indexOf('HW Plant')>=0, true);
document.querySelector('[data-add="plant"]').click();
ok('named for the hot-water sheet', curSvc().nodes.filter(function(n){return n.type==='plant';}).pop().name, 'HW PLANT');
deleteSelected();

note('=== choosing "Gas" on the hot-water sheet is what creates the gas copy ===');
switchService('hw');
var hp=curSvc().nodes.filter(function(n){return n.type==='plant';})[0];
selectNode_(hp.id);
// start from electric with nothing on the gas sheet
document.querySelector('#ptype').value='elec_central';
document.querySelector('#ptype').dispatchEvent(new Event('change',{bubbles:true}));
switchService('gas');
curSvc().pipes=curSvc().pipes.filter(function(p){    // unwire so the mirror can be dropped
  var m=curSvc().nodes.filter(function(n){return n.type==='plant';})[0];
  return !m || !((p.a&&p.a.node===m.id)||(p.b&&p.b.node===m.id));
});
syncGasPlants();
ok('electric plant: no gas copy', curSvc().nodes.filter(function(n){return n.type==='plant';}).length, 0);

switchService('hw');
selectNode_(hp.id);
document.querySelector('#ptype').value='gas_central';
document.querySelector('#ptype').dispatchEvent(new Event('change',{bubbles:true}));
ok('picking Gas creates the copy immediately, without leaving the sheet',
   state.services.gas.nodes.filter(function(n){return n.type==='plant';}).length, 1);
var mir=state.services.gas.nodes.filter(function(n){return n.type==='plant';})[0];
ok('at the hot-water plant position', mir.x+','+mir.y, hp.x+','+hp.y);
ok('and it is a gas load with no dwellings', mir.linkedTo, hp.id);

note('--- a load typed on the hot-water sheet reaches the gas sheet ---');
var gf=document.querySelector('#pgas');
gf.value='4500'; gf.dispatchEvent(new Event('input',{bubbles:true}));
ok('load written through', mir.gasLoad, 4500);
var nf=document.querySelector('#pname');
nf.value='ROOF BOILERS'; nf.dispatchEvent(new Event('input',{bubbles:true}));
ok('name written through', mir.name, 'ROOF BOILERS');

note('--- moving the plant on the hot-water sheet moves the gas copy ---');
hp.x=hp.x+120; syncGasPlants();
ok('the copy followed', mir.x, hp.x);

note('--- until the gas copy is placed by hand, after which it stays put ---');
mir.x=999; mir.y=111;              // as a drag would leave it
hp.x=hp.x+200; syncGasPlants();
ok('hand-placed copy is not yanked back', mir.x, 999);
ok('but it still shares the load', (function(){ hp.gasLoad=7777; syncGasPlants(); return mir.gasLoad; })(), 7777);

note('--- deleting the hot-water plant ---');
state.services.hw.nodes=state.services.hw.nodes.filter(function(n){return n.id!==hp.id;});
syncGasPlants();
ok('an unwired copy goes with it', state.services.gas.nodes.filter(function(n){return n.type==='plant';}).length, 0);

note('--- a wired copy survives instead of silently deleting drawn pipework ---');
switchService('hw');
var hp2={id:nid(),type:'plant',x:200,y:60,name:'HW PLANT 2',plantType:'gas_central',gasLoad:1000};
state.services.hw.nodes.push(hp2);
syncGasPlants();
var mir2=state.services.gas.nodes.filter(function(n){return n.type==='plant';})[0];
ok('copy created', !!mir2, true);
state.services.gas.pipes.push({id:nid(),pts:[{x:0,y:0},{x:10,y:10}],a:{node:mir2.id},b:null});
state.services.hw.nodes=state.services.hw.nodes.filter(function(n){return n.id!==hp2.id;});
syncGasPlants();
var still=state.services.gas.nodes.filter(function(n){return n.type==='plant';})[0];
ok('wired copy kept', !!still, true);
ok('but no longer linked to anything', still.linkedTo, undefined);
