(() => {
'use strict';
const BUILD='20260928.8', THEME_KEY='continuity.theme';
const THEMES=Object.freeze({system:{label:'System',native:'system'},dark:{label:'Dark',native:'dark'},oled:{label:'OLED Dark',native:'oled-dark'},wbw:{label:'World Between Worlds',native:'world-between-worlds'},lcars:{label:'LCARS',owned:true}});
const VOICES=Object.freeze({
 'ahsoka-pocket-hybrid-ep':{label:'Ahsoka Hybrid'},ahsoka:{label:'Ahsoka Piper (reference)',reference:true},cortana:{label:'Cortana'},'majel-computer':{label:'Majel Computer'}
});
const nativeTheme=(id)=>{const v=THEMES[id]?.native;if(!v)return false;localStorage.theme=v;localStorage.setItem('theme',v);document.documentElement.dataset.continuityTheme=id;window.dispatchEvent(new StorageEvent('storage',{key:'theme',newValue:v}));return true};
const api={version:'0.2.1',build:BUILD,themes:THEMES,voices:VOICES,
 setTheme(id){if(!THEMES[id])throw Error('Unknown theme: '+id);if(id==='lcars'){if(!window.OWUILCARS)throw Error('LCARS runtime unavailable');window.OWUILCARS.enable();localStorage.setItem(THEME_KEY,id);document.documentElement.dataset.continuityTheme=id}else{window.OWUILCARS?.disable();nativeTheme(id);localStorage.setItem(THEME_KEY,id)}window.dispatchEvent(new CustomEvent('continuity-shell:theme',{detail:{id}}));return id},
 theme(){return document.documentElement.classList.contains('lcars')?'lcars':(localStorage.getItem(THEME_KEY)||'system')},
 setVoice(id){if(!VOICES[id])throw Error('Unknown voice: '+id);return window.OWUIClientVoice?.setVoice(id)??false},
 voice(){return window.OWUIClientVoice?.status?.().voice||null}
};
window.ContinuityShell=Object.freeze(api);document.documentElement.dataset.continuityTheme=api.theme();
window.dispatchEvent(new CustomEvent('continuity-shell:ready',{detail:{version:api.version,build:BUILD}}));
})();
