// scripts/update.mjs
// Pulls World Cup 2026 results from football-data.org (free tier, competition "WC")
// and rewrites data.json with fresh results, fixtures and per-team status.
// Your authored "strength" ratings, players and avatars are preserved untouched.
//
// Needs Node 18+ (global fetch). Run: FOOTBALL_DATA_TOKEN=xxxx node scripts/update.mjs

import { readFile, writeFile } from "node:fs/promises";

const TOKEN = process.env.FOOTBALL_DATA_TOKEN;
const DATA_PATH = new URL("../data.json", import.meta.url);

if (!TOKEN) { console.error("Missing FOOTBALL_DATA_TOKEN env var."); process.exit(1); }

/* Map football-data.org team names -> the short names used in data.json */
const NAME_MAP = {
  "United States":"USA","USA":"USA","Korea Republic":"Korea","South Korea":"Korea",
  "Bosnia and Herzegovina":"Bosnia","Bosnia & Herzegovina":"Bosnia","Bosnia-Herzegovina":"Bosnia","Türkiye":"Turkey","Turkey":"Turkey",
  "Curaçao":"Curacao","Côte d'Ivoire":"Ivory Coast","Ivory Coast":"Ivory Coast",
  "Cabo Verde":"Cape Verde","Cape Verde":"Cape Verde","Cape Verde Islands":"Cape Verde","Czech Republic":"Czechia","Czechia":"Czechia",
  "IR Iran":"Iran","Iran":"Iran","Congo DR":"DR Congo","DR Congo":"DR Congo","Saudi Arabia":"Saudi Arabia"
};
const STRIP = s => (s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z]/g,"");

const STAGE_RANK = { GROUP:0, LAST_32:1, LAST_16:2, QUARTER_FINALS:3, SEMI_FINALS:4, THIRD_PLACE:5, FINAL:5 };
const fmtDate = iso => new Date(iso).toLocaleDateString("en-US",{month:"short",day:"numeric",timeZone:"UTC"});

async function main(){
  const data = JSON.parse(await readFile(DATA_PATH,"utf8"));
  const teamKeys = Object.keys(data.teams);
  const keyByStrip = Object.fromEntries(teamKeys.map(k=>[STRIP(k),k]));

  const resolve = name => {
    if (!name) return null;
    if (NAME_MAP[name]) return NAME_MAP[name];
    if (data.teams[name]) return name;
    const hit = keyByStrip[STRIP(name)];
    if (hit) return hit;
    console.warn("Unmapped team name:", name);
    return null;
  };

  const res = await fetch("https://api.football-data.org/v4/competitions/WC/matches",
    { headers:{ "X-Auth-Token": TOKEN } });
  if (!res.ok){ console.error("API error", res.status, await res.text()); process.exit(1); }
  const { matches } = await res.json();

  // reset live fields
  for (const k of teamKeys){ const t=data.teams[k]; t.gp=0; t.pts=0; t.stage="GROUP"; t.eliminated=false; }

  const finished=[], upcoming=[];
  let knockoutExists=false;
  const inKnockout=new Set();

  for (const m of matches){
    const a=resolve(m.homeTeam?.name), b=resolve(m.awayTeam?.name);
    if(!a||!b) continue;
    const stage = m.stage==="GROUP_STAGE" ? "GROUP" : m.stage;
    const group = (m.group||"").replace("GROUP_","").replace("Group ","").trim();
    // advance each team's furthest stage
    for(const t of [a,b]){
      if((STAGE_RANK[stage]??0) > (STAGE_RANK[data.teams[t].stage]??0)) data.teams[t].stage=stage;
    }
    if(stage!=="GROUP"){ knockoutExists=true; inKnockout.add(a); inKnockout.add(b); }

    if(m.status==="FINISHED"){
      const hs=m.score.fullTime.home, as=m.score.fullTime.away;
      finished.push({ date:fmtDate(m.utcDate), a, as:hs, b, bs:as, group, _utc:m.utcDate });
      if(stage==="GROUP"){
        data.teams[a].gp++; data.teams[b].gp++;
        if(hs>as) data.teams[a].pts+=3; else if(as>hs) data.teams[b].pts+=3;
        else { data.teams[a].pts++; data.teams[b].pts++; }
      } else {
        // knockout: the loser is out (no draws in knockouts after ET/pens)
        const w=m.score.winner; // HOME_TEAM | AWAY_TEAM
        if(w==="HOME_TEAM") data.teams[b].eliminated=true;
        else if(w==="AWAY_TEAM") data.teams[a].eliminated=true;
      }
    } else {
      upcoming.push({ utc:m.utcDate, group, a, b, _ts:new Date(m.utcDate).getTime() });
    }
  }

  // group-stage eliminations: only once knockouts are set and team has finished its 3 group games
  if(knockoutExists){
    for(const k of teamKeys){
      const t=data.teams[k];
      if(t.stage==="GROUP" && t.gp>=3 && !inKnockout.has(k)) t.eliminated=true;
    }
  }

  finished.sort((x,y)=> new Date(x._utc)-new Date(y._utc));
  finished.forEach(m=>delete m._utc);
  if(finished.length){
    const last=finished[finished.length-1];
    last.lastLabel=`${last.a}–${last.b}`;
    data.meta.updatedTill=`${last.a}–${last.b}`;
    data.meta.updatedDate=last.date;
  }
  data.meta.lastSync=new Date().toISOString();

  upcoming.sort((x,y)=>x._ts-y._ts);
  data.matches=finished;
  data.upcoming=upcoming.slice(0,8).map(({_ts,...m})=>m);

  await writeFile(DATA_PATH, JSON.stringify(data,null,2)+"\n");
  console.log(`Updated: ${finished.length} finished, ${data.upcoming.length} upcoming. Through ${data.meta.updatedTill}.`);
}

main().catch(e=>{ console.error(e); process.exit(1); });
