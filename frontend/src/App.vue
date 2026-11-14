<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from './api'
import Designer from './components/Designer.vue'
const token = ref(localStorage.getItem('kfd_token') || '')
const username = ref('admin'), password = ref('')
const error = ref(''), dark = ref(localStorage.getItem('kfd_theme') === 'dark')
const page = ref<'designer'|'instances'|'projects'>('designer')
const instances = ref<any[]>([]), projects = ref<any[]>([])
const selectedInstance = ref(''), selectedRealm = ref('')
const project = ref<any>(null)
function theme(){document.documentElement.dataset.theme=dark.value?'dark':'light';localStorage.setItem('kfd_theme',dark.value?'dark':'light')}
async function login(){try{const body=new URLSearchParams({username:username.value,password:password.value});const r=await api.post('/auth/login',body,{headers:{'Content-Type':'application/x-www-form-urlencoded'}});token.value=r.data.access_token;localStorage.setItem('kfd_token',token.value);error.value='';await load()}catch(e:any){error.value=e.response?.data?.detail||'Connexion impossible'}}
function logout(){token.value='';localStorage.removeItem('kfd_token')}
async function load(){if(!token.value)return;try{instances.value=(await api.get('/instances')).data;projects.value=(await api.get('/projects')).data;if(!project.value) newProject()}catch{logout()}}
function newProject(){project.value={schemaVersion:'1.0',project:{id:crypto.randomUUID(),name:'Nouveau parcours',description:''},flow:{alias:'browser-custom',description:'',topLevel:true,providerId:'basic-flow',nodes:[]}}}
async function save(){try{const r=await api.post('/projects',project.value);project.value=r.data;await load()}catch(e:any){error.value=e.response?.data?.detail||'Sauvegarde impossible'}}
async function addInstance(){const name=prompt('Nom de l’instance');if(!name)return;const base_url=prompt('URL Admin REST (ex. https://sso.example.com)');if(!base_url)return;const token_url=prompt('URL token (ex. https://sso.example.com/realms/master/protocol/openid-connect/token)');if(!token_url)return;const client_id=prompt('Client ID du compte de service');if(!client_id)return;const client_secret=prompt('Client secret');if(!client_secret)return;await api.post('/instances',{name,base_url,token_url,client_id,client_secret,verify_tls:true});await load()}
async function openProject(id:string){project.value=(await api.get('/projects/'+id)).data;page.value='designer'}
onMounted(()=>{theme();load()})
</script>
<template>
  <div v-if="!token" class="login-shell">
    <form class="login-card" @submit.prevent="login"><div class="brand-mark">K</div><h1>Keycloak Flow Designer</h1><p>Concevoir et gérer les parcours d’authentification</p><label>Utilisateur<input v-model="username" autocomplete="username"></label><label>Mot de passe<input v-model="password" type="password" autocomplete="current-password"></label><button class="primary">Se connecter</button><p v-if="error" class="error">{{error}}</p></form>
  </div>
  <div v-else class="app-shell">
    <header class="topbar"><div class="brand"><span class="brand-mark small">K</span><b>Flow Designer</b></div><div class="top-actions"><span class="muted">{{username}}</span><button class="icon-btn" @click="dark=!dark;theme()" :title="dark?'Mode clair':'Mode sombre'">{{dark?'☀':'◐'}}</button><button class="ghost" @click="logout">Déconnexion</button></div></header>
    <div class="layout"><aside class="sidebar"><div class="nav-title">ESPACE DE TRAVAIL</div><button :class="{active:page==='designer'}" @click="page='designer'">⌘　Designer</button><button :class="{active:page==='projects'}" @click="page='projects'">▤　Projets</button><button :class="{active:page==='instances'}" @click="page='instances'">◎　Instances Keycloak</button><div class="sidebar-bottom"><span class="status-dot"></span> Stockage local JSON</div></aside>
      <main class="main">
        <template v-if="page==='designer'"><div class="page-head"><div><div class="eyebrow">ÉDITEUR DE WORKFLOWS</div><h2>{{project?.project?.name}}</h2><p class="muted">Construisez un parcours avec les composants natifs de Keycloak.</p></div><div class="head-actions"><button class="ghost" @click="newProject">Nouveau</button><button class="primary" @click="save">Enregistrer</button></div></div><Designer v-if="project" v-model="project" :instances="instances" /></template>
        <template v-else-if="page==='instances'"><div class="page-head"><div><div class="eyebrow">CONNEXIONS</div><h2>Instances Keycloak</h2><p class="muted">Gérez les connexions aux serveurs et leurs Realms.</p></div><button class="primary" @click="addInstance">Ajouter une instance</button></div><div class="cards"><div v-for="i in instances" :key="i.id" class="panel"><b>{{i.name}}</b><p class="muted">{{i.base_url}}</p><button class="ghost" @click="api.post('/instances/'+i.id+'/test').then(()=>alert('Connexion réussie')).catch(()=>alert('Échec de connexion'))">Tester la connexion</button></div><p v-if="!instances.length" class="empty">Aucune instance configurée.</p></div></template>
        <template v-else><div class="page-head"><div><div class="eyebrow">BIBLIOTHÈQUE</div><h2>Projets</h2><p class="muted">Workflows sauvegardés localement.</p></div><button class="primary" @click="newProject();page='designer'">Nouveau projet</button></div><div class="cards"><button v-for="p in projects" :key="p.id" class="panel project-card" @click="openProject(p.id)"><b>{{p.name}}</b><small class="muted">{{p.updatedAt||''}}</small></button><p v-if="!projects.length" class="empty">Aucun projet sauvegardé.</p></div></template>
        <p v-if="error" class="error">{{error}}</p>
      </main>
    </div>
  </div>
</template>
