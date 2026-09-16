// ---- UI suite: every gas panel / drawing path must render without throwing, and the sheet
// switch must leave the cold and hot sheets alone.

function panelText(){ return document.getElementById('p-body').textContent; }
function svgText(){ return document.getElementById('board').textContent; }

note('--- build a gas sheet through the real entry points ---');
state.building={job:{name:'UI TEST',number:'99999'},
  levels:['GF','LEVEL 1','LEVEL 2','LEVEL 3','LEVEL 4','LEVEL 5'], groundIdx:0};
switchService('cw');
var cw=curSvc(); cw.nodes=[]; cw.pipes=[]; state.nextId=1;
var csrc={id:nid(),type:'source',x:160,y:levelY(0)+56,name:'MAINS SUPPLY'};
var cr={id:nid(),type:'riser',x:420,name:'CW RISER 1',start:0,
  data:state.building.levels.map(function(){return blankLevel();}),rl:blankRl()};
for(var i=0;i<6;i++) cr.data[i].dwellings=8;
cw.nodes.push(csrc,cr);
var ca={node:cr.id,level:0}, cq=attachPoint(ca);
cw.pipes.push({id:nid(),pts:[{x:csrc.x,y:csrc.y},{x:cq.x,y:csrc.y},{x:cq.x,y:cq.y}],a:{node:csrc.id},b:ca});
render();
ok('cold sheet drew', svgText().indexOf('CW')>=0, true);

// switching to an empty gas sheet auto-builds from the cold-water risers
switchService('gas');
ok('gas auto-build made a riser', allRisers().length, 1);
ok('gas riser inherited the dwellings', allRisers()[0].data[3].dwellings, 8);
ok('gas riser name swapped CW->GAS', allRisers()[0].name.indexOf('GAS')>=0, true);
ok('gas sheet has a supply node', curSvc().nodes.filter(function(n){return n.type==='source';}).length, 1);
ok('gas supply is fed from below (bottom-fed)', riserInfo[allRisers()[0].id].feed, 0);
ok('gas theme class applied', document.documentElement.classList.contains('svc-gas'), true);
ok('water toolbar group hidden', document.getElementById('grp-water').style.display, 'none');
ok('gas toolbar group shown', document.getElementById('grp-gas').style.display, '');
ok('brand subtitle', document.querySelector('.brand span').textContent.indexOf('Gas')>=0, true);

note('--- the gas drawing ---');
render();
var s=svgText();
ok('meter branches say GAS METERS', s.indexOf('x GAS METERS')>=0, true);
ok('callouts are MJ/hr, not L/s', s.indexOf('MJ/hr')>=0, true);
ok('no velocity callout on the gas sheet', s.indexOf('m/s'), -1);
ok('riser has diameter callouts', /Ø\d+/.test(s), true);

note('--- gas riser panel ---');
selectNode_(allRisers()[0].id);
var pt=panelText();
ok('riser panel shows the gas overrides', pt.indexOf('Gas sizing')>=0, true);
ok('riser panel shows index length', pt.indexOf('Index length')>=0, true);
ok('riser panel shows the diversity factor', pt.indexOf('Diversity factor')>=0, true);
ok('riser panel shows adjusted demand', pt.indexOf('Adjusted demand')>=0, true);
ok('no velocity override on gas', pt.indexOf('Max vel'), -1);
ok('no pressure block on gas', pt.indexOf('pump duty'), -1);
ok('level editor has the plant column', pt.indexOf('Plant MJ/hr')>=0, true);
ok('level badges read in MJ/hr', pt.indexOf('MJ/hr')>=0, true);

note('--- editing through the panel widgets ---');
var mjInput=document.querySelector('#levels input[data-f="mj"]');
ok('plant-load input exists', !!mjInput, true);
mjInput.value='1500'; mjInput.dispatchEvent(new Event('input',{bubbles:true}));
ok('typing a plant load lands on the model', allRisers()[0].data[5].mj, 1500);
allRisers()[0].data[5].mj=0;

var idxSel=document.querySelector('.gasf[data-gas="indexLength"]');
ok('index length is a fixed list, not free text', idxSel.tagName, 'SELECT');
ok('index length list matches the tables', idxSel.options.length, gasLengths().length+1);

note('--- gas pipe panel ---');
selectPipe_(curSvc().pipes[0].id);
var pp=panelText();
ok('pipe panel is the gas one', pp.indexOf('Adjusted demand')>=0, true);
ok('pipe panel names the table', pp.indexOf('F.')>=0, true);
ok('pipe panel shows size options', pp.indexOf('one size down')>=0, true);
ok('pipe panel shows capacities', pp.indexOf('Table capacity')>=0, true);
ok('pipe panel has no velocity', pp.indexOf('m/s'), -1);

note('--- building panel on the gas sheet ---');
selectNone();
ok('building panel mentions GAS CALCS', panelText().indexOf('GAS CALCS')>=0, true);

note('--- toolbar controls drive the sheet ---');
var tsel=document.getElementById('gas-table');
tsel.value='f13'; tsel.dispatchEvent(new Event('change',{bubbles:true}));
ok('table select changes the sheet', supplyGas().table, 'f13');
tsel.value='f12'; tsel.dispatchEvent(new Event('change',{bubbles:true}));
document.getElementById('btn-gas-div').click();
ok('diversity toggles off', supplyGas().diversity, false);
document.getElementById('btn-gas-div').click();
ok('diversity toggles back on', supplyGas().diversity, true);

note('--- PDF naming picks up the gas sheet ---');
ok('pdf filename', pdfName(), '99999 Gas Schematic');
switchService('cw');
ok('pdf filename back on cold', pdfName(), '99999 Cold Water Schematic');

note('--- the cold sheet survived all of that ---');
render();
ok('cold riser still there', allRisers().length, 1);
ok('cold sheet still sizes in L/s', svgText().indexOf('L/s')>=0, true);
ok('cold theme restored', document.documentElement.classList.contains('svc-gas'), false);
selectNode_(allRisers()[0].id);
ok('cold riser panel still has velocity', panelText().indexOf('Max vel')>=0, true);
ok('cold riser panel still has pressure', panelText().indexOf('Pressure')>=0, true);

// undo commits its snapshot on a deferred tick, so these run a turn later
note('--- undo covers the gas sheet (deferred) ---');
switchService('gas');
var beforeIdx=supplyGas().indexLength;
var isel=document.getElementById('gas-index');
isel.value='320'; isel.dispatchEvent(new Event('change',{bubbles:true}));
ok('index length changed', supplyGas().indexLength, 320);
defer(function(){
  ok('the change made an undo step', undoStack.length>0, true);
  undo();
  ok('undo restores the index length', supplyGas().indexLength, beforeIdx);
  ok('undo left us on the gas sheet', state.activeService, 'gas');
  ok('the toolbar followed the undo', document.getElementById('gas-index').value, String(beforeIdx));
  redo();
  ok('redo re-applies it', supplyGas().indexLength, 320);
});
