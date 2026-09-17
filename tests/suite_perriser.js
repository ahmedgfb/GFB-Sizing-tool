// ---- per-riser demand/dwelling: the override must survive typing, and must follow the load
// all the way up a shared main.

note('--- build two risers with different appliance loads ---');
state.building={job:{name:'MIXED',number:'55555'},
  levels:['GROUND','LEVEL 1','LEVEL 2','LEVEL 3','LEVEL 4','LEVEL 5'], groundIdx:0};
switchService('gas');
var gs=curSvc(); gs.nodes=[]; gs.pipes=[]; state.nextId=1;
Object.assign(supplyGas(), {table:'f12', indexLength:200, demandPerDwelling:40, diversity:true, tolerancePct:''});
var src={id:nid(),type:'source',x:160,y:levelY(0)+56,name:'GAS SUPPLY'};
gs.nodes.push(src);
function mkRiser(x,name,dw){
  var r={id:nid(),type:'riser',x:x,name:name,start:0,
    data:state.building.levels.map(function(){return blankLevel();}),rl:blankRl(),gas:blankGas()};
  for(var i=0;i<6;i++) r.data[i].dwellings=dw;
  gs.nodes.push(r); return r;
}
var r1=mkRiser(420,'GAS RISER 1',4);   // 24 dwellings
var r2=mkRiser(760,'GAS RISER 2',3);   // 18 dwellings
var a1={node:r1.id,level:0}, q1=attachPoint(a1);
gs.pipes.push({id:nid(),pts:[{x:src.x,y:src.y},{x:q1.x,y:src.y},{x:q1.x,y:q1.y}],a:{node:src.id},b:a1});
var a2={node:r2.id,level:0}, q2=attachPoint(a2);
gs.pipes.push({id:nid(),pts:[{x:q1.x,y:q1.y},{x:q2.x,y:q1.y},{x:q2.x,y:q2.y}],a:a1,b:a2});
var incoming=gs.pipes[0].id, between=gs.pipes[1].id;

note('--- riser 2 runs 60 MJ/hr appliances, riser 1 stays on the sheet default of 40 ---');
r2.gas.demandPerDwelling=60;
var res=sizePipes();
ok('riser 2 own load uses 60', Math.round(sizeGasLoad(riserGasLoad(r2),resolveGas(r2)).mj*100)/100,
   Math.round(18*60*gasDiversity(18)*100)/100);
ok('riser 1 own load still uses 40', Math.round(sizeGasLoad(riserGasLoad(r1),resolveGas(r1)).mj*100)/100,
   Math.round(24*40*gasDiversity(24)*100)/100);
ok('run between the risers = riser 2 alone', Math.round(res[between].mj*100)/100,
   Math.round(18*60*gasDiversity(18)*100)/100);

// The incoming main carries 24 dwellings at 40 and 18 at 60. Diversity keys off the TOTAL count
// (42), but the undiversified demand must respect each riser's own rate.
var want = (24*40 + 18*60) * gasDiversity(42);
ok('incoming main dwellings', res[incoming].dwellings, 42);
ok('incoming main respects both rates', Math.round(res[incoming].mj*100)/100, Math.round(want*100)/100);
note('a single sheet-wide 40 MJ/hr would give '+Math.round(42*40*gasDiversity(42))+' MJ/hr instead');

note('--- and it still matches the workbook when the rates are equal ---');
r2.gas.demandPerDwelling='';
res=sizePipes();
ok('uniform rate = the MAIN PIPE formula', Math.round(res[incoming].mj*100)/100,
   Math.round(42*40*gasDiversity(42)*100)/100);

note('--- typing into the override must not lose focus after one character ---');
r2.gas.demandPerDwelling='';
selectNode_(r2.id);
var fld=document.querySelector('.gasf[data-gas="demandPerDwelling"]');
ok('the field is there', !!fld, true);
fld.focus();
ok('focused', document.activeElement===fld, true);
// type "6" then "0", the way a person does
fld.value='6'; fld.dispatchEvent(new Event('input',{bubbles:true}));
ok('still focused after the 1st character', document.activeElement===fld, true);
ok('field still in the document', document.contains(fld), true);
fld.value='60'; fld.dispatchEvent(new Event('input',{bubbles:true}));
ok('still focused after the 2nd character', document.activeElement===fld, true);
ok('the model took 60, not 6', +r2.gas.demandPerDwelling, 60);
ok('the drawing followed', sizeGasLoad(riserGasLoad(r2),resolveGas(r2)).mj > 0, true);

note('--- the readout under the panel keeps up without a rebuild ---');
ok('riser readout shows the overridden demand',
   document.getElementById('p-body').textContent.indexOf('MJ/hr')>=0, true);

note('--- index length and diversity selects still work ---');
var isel=document.querySelector('.gasf[data-gas="indexLength"]');
isel.value='120'; isel.dispatchEvent(new Event('change',{bubbles:true}));
ok('index length override lands', +r2.gas.indexLength, 120);
var dsel=document.querySelector('.gasf[data-gas="diversity"]');
dsel.value='off'; dsel.dispatchEvent(new Event('change',{bubbles:true}));
ok('diversity override lands', r2.gas.diversity, 'off');
ok('diversity off means undiversified', sizeGasLoad(riserGasLoad(r2),resolveGas(r2)).mj, 18*60);

note('--- a mixed main says so, rather than showing one riser\'s rate ---');
r2.gas.indexLength=''; r2.gas.diversity=''; r2.gas.demandPerDwelling=60;
sizePipes();
selectPipe_(incoming);
var pt=document.getElementById('p-body').textContent;
ok('pipe panel shows the blended rate', pt.indexOf('blended')>=0, true);
ok('pipe panel explains why', pt.indexOf('at its own')>=0, true);
selectPipe_(between);
var pt2=document.getElementById('p-body').textContent;
ok('a single-riser run is not labelled blended', pt2.indexOf('blended'), -1);
ok('and shows that riser\'s own 60', pt2.indexOf('60 MJ/hr')>=0, true);

note('--- riser panel names where the rate came from ---');
selectNode_(r2.id);
ok('overridden riser says "this riser"', document.getElementById('p-body').textContent.indexOf('(this riser)')>=0, true);
selectNode_(r1.id);
ok('inheriting riser says "sheet"', document.getElementById('p-body').textContent.indexOf('(sheet)')>=0, true);
