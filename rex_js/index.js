import tls from 'tls';
import http2 from 'http2';
import colors from '@colors/colors';
import { Client } from 'discord.js-selfbot-v13';
import { readFile } from 'fs/promises';
const config = JSON.parse(await readFile(new URL('./config.json', import.meta.url)));

const asciiArt = colors.red(`
    ░▒▓███████▓▒░░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░       ░▒▓███████▓▒░▒▓███████▓▒░░▒▓█▓▒░▒▓███████▓▒░░▒▓████████▓▒░▒▓███████▓▒░  
    ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░ 
    ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░ 
    ░▒▓███████▓▒░░▒▓██████▓▒░  ░▒▓██████▓▒░ ░▒▓██████▓▒░        ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓███████▓▒░░▒▓██████▓▒░ ░▒▓███████▓▒░  
    ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░             ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░ 
    ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░             ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░ 
    ░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓███████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░ 
`);
    
const availableColors = ['green', 'yellow', 'blue', 'magenta', 'cyan', 'white'];
    
function getCurrentTime() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    const seconds = now.getSeconds().toString().padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
}
    
function coloredMessage(...args) {
    console.log(randomColor(`[${getCurrentTime()}] ${args.join(' ')}`));
}
    
function coloredError(...args) {
    console.error(randomColor(`[${getCurrentTime()}] ${args.join(' ')}`));
}
    
function randomColor(text) {
    const color = availableColors[Math.floor(Math.random() * availableColors.length)];
    return colors[color](text);
}

const client = new Client();
const { token, channelId, serverId, userToDm, password, webhookUrl } = config;

let mfaIntervalId, sniperProcess = true, isAutokickEnabled = false, mfaToken;
let lastMfaVerifyTime = 0;
let requestSent = false;
let hasSuccessfullySnipedVanity = false;
let hasExistingVanity = false;

const now = () => {
    const d = new Date(), pad = n => n.toString().padStart(2, '0'),
        ms = d.getMilliseconds().toString().padStart(3, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}:${ms}`;
};

const sendMessage = (id, msg) => {
    const ch = client.channels.cache.get(id);
    if (ch) ch.send(msg).catch(err => coloredError(err));
};

const sendWebhook = async (embed) => {
    try {
        await fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ embeds: [embed], content: "@everyone" })
        });
    } catch (error) {
        coloredError('Webhook error:', error);
    }
};

client.on('guildMemberAdd', async member => {
    if (isAutokickEnabled && member.guild.id === serverId) {
        try {
            await member.kick('ReXx X Vanity Sniper');
        } catch (error) {
            coloredError(`Failed to kick member ${member.user.tag}: ${error.message}`);
        }
    }
});

client.on('guildUpdate', async (oldG, newG) => {
    const oldCode = oldG.vanityURLCode;
    const newCode = newG.vanityURLCode;

    if (oldCode !== newCode) {
        coloredMessage(`Vanity changed: ${oldCode || 'none'} -> ${newCode || 'none'}`);
        sendMessage(
            channelId,
            `\`${newCode}\` *${now()}* ||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||ً @everyone @here`
        );

        if (!requestSent && sniperProcess === true && !hasSuccessfullySnipedVanity) {
            requestSent = true;
            coloredMessage(`update: ${oldCode} -> ${newCode}. Sending patch request...`);

            
            try {
                const targetGuild = await client.guilds.fetch(serverId);
                hasExistingVanity = !!targetGuild.vanityURLCode;
                
                if (hasExistingVanity) {
                    coloredMessage(`Target server already has vanity URL: ${targetGuild.vanityURLCode}. Sending notification only.`);
                    
                    const notificationEmbed = {
                        title: "Vanity Available for Snipe",
                        description: `The vanity URL \`${oldCode}\` is available to snipe, but your server already has a vanity.`,
                        color: 0xffaa00,
                        fields: [
                            { name: "Available Vanity", value: oldCode, inline: true },
                            { name: "Your Current Vanity", value: targetGuild.vanityURLCode, inline: true },
                            { name: "Server ID", value: serverId, inline: true }
                        ],
                        timestamp: new Date().toISOString(),
                        footer: { text: "ReXx X Vanity Sniper" }
                    };
                    
                    await sendWebhook(notificationEmbed);
                    requestSent = false;
                    return;
                }
            } catch (err) {
                coloredError('Error checking target server:', err);
            }

            const requestBody = { code: oldCode };
            try {
                const startTime = Date.now();
                const res = await rex.request(
                    "PATCH",
                    `/api/v10/guilds/${serverId}/vanity-url`,
                    {
                        'X-Discord-MFA-Authorization': mfaToken,
                        Cookie: `__Secure-recent_mfa=${mfaToken}`,
                        "Content-Type": "application/json"
                    },
                    JSON.stringify(requestBody)
                );
                
                const endTime = Date.now();
                const timeTaken = (endTime - startTime);
                const formattedTime = (timeTaken / 1000).toFixed(3);
                
                coloredMessage('Request successful, (http2) response =>', res);
                sendMessage(channelId, `\`${res}\` *${now()}* request successful.`);
                
                let response;
                try {
                    response = JSON.parse(res);
                } catch (e) {
                    response = { message: "Unable to parse response" };
                }
                
                if (response.code === oldCode) {
                    hasSuccessfullySnipedVanity = true;
                    
                    const successEmbed = {
                        title: "Vanity Captured",
                        description: `\`\`\`Successfully captured discord.gg/${oldCode}\`\`\``,
                        color: 0x00ff00,
                        fields: [
                            {
                                name: "Claim Speed",
                                value: `\`\`\`${formattedTime}s\`\`\``,
                                inline: false
                            },
                        ],
                    };
                    
                    await sendWebhook(successEmbed);
                    
                    try {
                        const user = await client.users.fetch(userToDm);
                        if (user) {
                            const dmMessage = `🎯 **Vanity Snipe Successful!**\n\n` +
                                `▸ **Vanity:** \`${oldCode}\`\n` +
                                `▸ **Speed:** \`${formattedTime}s\`\n` +
                                `✅ Successfully claimed for your server!`;
                            await user.send(dmMessage);
                        }
                    } catch (dmError) {
                        coloredError('Failed to send DM:', dmError);
                    }
                } else {
                    const errorEmbed = {
                        title: "Failed to Capture Vanity",
                        description: `\`\`\`Failed to capture discord.gg/${oldCode}\`\`\``,
                        color: 0xff0000,
                        fields: [
                            { name: "Error", value: `\`\`\`${response.message || "Unknown error"}\`\`\``, inline: false },
                            { name: "Time Taken", value: `\`\`\`${formattedTime}s\`\`\``, inline: true },
                        ],
                    };
                    
                    await sendWebhook(errorEmbed);
                }
            } catch (err) {
                coloredError('http2 error:', err);
                const errorEmbed = {
                    title: "❌ Failed to Snipe Vanity",
                    description: `Failed to snipe \`${oldCode}\``,
                    color: 0xff0000,
                    fields: [
                        { name: "Error", value: err.message || "Unknown error", inline: true },
                        { name: "Target Vanity", value: oldCode, inline: true },
                        { name: "Current Vanity", value: newCode || 'none', inline: true }
                    ],
                    timestamp: new Date().toISOString(),
                    footer: { text: "ReXx X Vanity Sniper" }
                };
                await sendWebhook(errorEmbed);
            } finally {
                requestSent = false;
            }
        } else if (hasSuccessfullySnipedVanity) {
            
            const availableVanityEmbed = {
                title: "Vanity URL Available",
                description: `The vanity URL \`${oldCode}\` is available, but you've already sniped a vanity.`,
                color: 0x3498db,
                fields: [
                    { name: "Available Vanity", value: oldCode, inline: true },
                    { name: "Detection Time", value: now(), inline: true }
                ],
                timestamp: new Date().toISOString(),
                footer: { text: "ReXx X Vanity Sniper" }
            };
            
            await sendWebhook(availableVanityEmbed);
        }
    }
});

client.on('guildDelete', g => {
    sendMessage(channelId, `*Vanity URL \`${g.vanityURLCode}\` was deleted at ${now()}*`);
    coloredMessage(`guild delete: ${g.vanityURLCode}`);
});

const help = message => {
    const helpMessage = `**Command List:**
    \`.help\` 
    \`.mfa\` – Enables MFA verification. Don't enable sniper without enabling this first.
    \`.leave\` – Leaves a server.
    \`.claim\` – Claims a vanity URL.
    \`.vanity\` – Lists vanity URLs in selfbot.
    \`.autokick\` – Toggles autokick.
    \`.pause\` – Pauses invites.
    \`.restart\` – Restarts the bot.
    \`.delete\` – Deletes vanity URL.
    \`.sniper\` – Enables or disables sniper. on / off
    \`.reset\` – Resets the sniper state to allow sniping another vanity.
        `;
    message.reply(helpMessage);
};

client.on('message', async message => {
    if (message.channel.id !== channelId) return;
    const [cmd, ...args] = message.content.split(' ');
    switch (cmd) {
        case '.help': return help(message);
        case '.mfa':
            if (!mfaIntervalId && args[0] === 'on') { ticket(); mfaIntervalId = setInterval(ticket, 270000); return message.reply('MFA verifying started.'); }
            if (mfaIntervalId && args[0] === 'off') { clearInterval(mfaIntervalId); mfaIntervalId = undefined; return message.reply('MFA stopped.'); }
            return message.reply('Specify `on` or `off`.');
        case '.leave': {
            const target = args[0];
            const guild = client.guilds.cache.find(g => g.vanityURLCode === target) || client.guilds.cache.get(target);
            return guild ? (await leave(guild.id), message.channel.send(`Left: \`${target}\``)) : message.channel.send('?');
        }
        case '.claim':
            if (!args.length) return message.reply('Please provide a vanity code to claim.');
            if (hasSuccessfullySnipedVanity) {
                return message.reply('You have already sniped a vanity. Use `.reset` to reset the sniper state.');
            }
            claimUrl(args.join(' '));
            return message.reply(`Claiming \`${args.join(' ')}\``);
        case '.vanity': return listVanities();
        case '.autokick': return autokick(message).catch(e => { coloredError(e.message); message.reply('Error processing autokick.'); });
        case '.pause': return pauseInvites();
        case '.restart': return process.exit(0);
        case '.delete': return deleteUrl();
        case '.sniper':
            if (args[0] === 'on') { sniperProcess = true; return message.reply('🔫 **Sniper enabled**'); }
            if (args[0] === 'off') { sniperProcess = false; return message.reply('⛔ **Sniper disabled**'); }
            return message.reply('Specify `on` or `off` for sniper.');
        case '.reset':
            hasSuccessfullySnipedVanity = false;
            hasExistingVanity = false;
            return message.reply('✅ Sniper state has been reset. Ready to snipe a new vanity URL.');
    }
});

const listVanities = () => {
    const urls = client.guilds.cache.filter(g => g.vanityURLCode);
    sendMessage(channelId, urls.size ? urls.map(g => `\`${g.vanityURLCode}\``).join(' ') : '?');
};

const pauseInvites = async () => {
    const until = new Date(Date.now() + 86400000).toISOString();
    try {
        const res = await fetch(`https://discord.com/api/v9/guilds/${serverId}/incident-actions`, {
            method: 'PUT',
            headers: {
                'Authorization': token,
                'Content-Type': 'application/json',
                'x-discord-locale': 'en-US',
                'x-discord-timezone': 'Europe/Istanbul'
            },
            body: JSON.stringify({ invites_disabled_until: until, dms_disabled_until: null })
        });
        await res.json();
        sendMessage(channelId, 'Invites disabled for \`24 hours\`.');
    } catch (e) { coloredError('Pause invite error:', e); }
};

const leave = async id => {
    try {
        const res = await fetch(`https://discord.com/api/v9/users/@me/guilds/${id}`, { method: 'DELETE', headers: { Authorization: token } });
        res.ok ? coloredMessage(`Left guild: ${id}`) : coloredError(`Failed to leave guild: ${id}`);
    } catch (e) { coloredError(`Leave error (${id}):`, e); }
};

async function autokick(message) {
    isAutokickEnabled = !isAutokickEnabled;
    sendMessage(channelId, isAutokickEnabled ? 'Autokick \`enabled\`.' : 'Autokick \`disabled\`.');
}

async function claimUrl(vanityCode) {
    
    if (hasSuccessfullySnipedVanity) {
        coloredMessage(`Already sniped a vanity, not attempting to claim ${vanityCode}`);
        sendMessage(channelId, `⚠️ Already sniped a vanity. Use \`.reset\` to reset the sniper state.`);
        return;
    }

    try {
        const targetGuild = await client.guilds.fetch(serverId);
        hasExistingVanity = !!targetGuild.vanityURLCode;
        
        if (hasExistingVanity) {
            coloredMessage(`Target server already has vanity URL: ${targetGuild.vanityURLCode}. Sending notification only.`);
            sendMessage(channelId, `⚠️ Your server already has vanity URL: \`${targetGuild.vanityURLCode}\`. Not claiming \`${vanityCode}\`.`);
            
            const notificationEmbed = {
                title: "Vanity Available for Claim",
                description: `The vanity URL \`${vanityCode}\` could be claimed, but your server already has a vanity.`,
                color: 0xffaa00,
                fields: [
                    { name: "Available Vanity", value: vanityCode, inline: true },
                    { name: "Your Current Vanity", value: targetGuild.vanityURLCode, inline: true },
                    { name: "Server ID", value: serverId, inline: true }
                ],
                timestamp: new Date().toISOString(),
                footer: { text: "ReXx X Vanity Sniper" }
            };
            
            await sendWebhook(notificationEmbed);
            return;
        }
    } catch (err) {
        coloredError('Error checking target server:', err);
    }

    try {
        const startTime = Date.now();
        const res = await rex.request("PATCH", `/api/v10/guilds/${serverId}/vanity-url`, {
            'X-Discord-MFA-Authorization': mfaToken,
            Cookie: `__Secure-recent_mfa=${mfaToken}`,
            'Content-Type': 'application/json'
        }, JSON.stringify({ code: vanityCode }));
        
        const endTime = Date.now();
        const timeTaken = (endTime - startTime);
        const formattedTime = (timeTaken / 1000).toFixed(2);
        
        let response;
        try {
            response = JSON.parse(res);
        } catch (e) {
            response = { message: "Unable to parse response" };
        }
        
        coloredMessage('Response:', JSON.stringify(response, null, 2));
        
        if (response.code === vanityCode || !response.message) {
            hasSuccessfullySnipedVanity = true;
            
            const successEmbed = {
                title: "Vanity Claimed",
                description: `**Claimed \`${vanityCode}\`** ✅`,
                color: 0x00ff00,
                fields: [
                    { name: "Claim Speed", value: `${formattedTime}s (${timeTaken}ms)`, inline: true },
                    { name: "Guild ID", value: serverId, inline: true }
                ],
                timestamp: new Date().toISOString()
            };
            
            await sendWebhook(successEmbed);
            
            try {
                const user = await client.users.fetch(userToDm);
                if (user) {
                    user.send(`✅ Claimed vanity \`${vanityCode}\` in ${formattedTime}s!`);
                }
            } catch (dmError) {
                coloredError('Failed to send DM:', dmError);
            }
        } else {
            const errorEmbed = {
                title: "Failed to Claim Vanity",
                description: `Failed to claim \`${vanityCode}\``,
                color: 0xff0000,
                fields: [
                    { name: "Error", value: response.message || "Unknown error", inline: true },
                    { name: "Guild ID", value: serverId, inline: true }
                ],
                timestamp: new Date().toISOString()
            };
            
            await sendWebhook(errorEmbed);
        }
    } catch (err) {
        coloredError('Error:', err);
        const errorEmbed = {
            title: "Failed to Claim Vanity",
            description: `Failed to claim \`${vanityCode}\``,
            color: 0xff0000,
            fields: [
                { name: "Error", value: err.message || "Unknown error", inline: true },
                { name: "Guild ID", value: serverId, inline: true }
            ],
            timestamp: new Date().toISOString()
        };
        await sendWebhook(errorEmbed);
    }
}  

async function deleteUrl() {
    try {
        const res = await rex.request("PATCH", `/api/v10/guilds/${serverId}/vanity-url`, {
            'X-Discord-MFA-Authorization': mfaToken,
            Cookie: `__Secure-recent_mfa=${mfaToken}`,
            'Content-Type': 'application/json'
        }, JSON.stringify({ code: "" }));
        
        let response;
        try {
            response = JSON.parse(res);
        } catch (e) {
            response = { message: "Unable to parse response" };
        }
        
        coloredMessage('Response:', JSON.stringify(response, null, 2));
        sendMessage(channelId, 'Vanity URL deleted successfully.');
        
        hasSuccessfullySnipedVanity = false;
        hasExistingVanity = false;
    } catch (err) {
        coloredError('HTTP2 error:', err);
        sendMessage(channelId, 'Failed to delete vanity URL.');
    }
}

class RexClient {
    constructor() { this.createSession(); }
    createSession() {
        this.session?.destroy();
        this.session = http2.connect("https://canary.discord.com", {
            settings: { noDelay: true },
            secureContext: tls.createSecureContext({ ciphers: 'ECDHE-RSA-AES128-GCM-SHA256:AES128-SHA' })
        });
        this.session.on('error', () => setTimeout(() => this.createSession(), 5000));
        this.session.on('close', () => setTimeout(() => this.createSession(), 5000));
    }
    async request(method, path, customHeaders = {}, body = null) {
        return new Promise((resolve, reject) => {
            const headers = { 
                'Content-Type': 'application/json',
                'Authorization': token, 
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) 1huz/1.0.1130 Chrome/128.0.6613.186 Electron/32.2.7 Safari/537.36', 
                'X-Super-Properties': 'eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJyZWxlYXNlX2NoYW5uZWwiOiJwdGIiLCJjbGllbnRfdmVyc2lvbiI6IjEuMC4xMTMwIiwib3NfdmVyc2lvbiI6IjEwLjAuMTkwNDUiLCJvc19hcmNoIjoieDY0IiwiYXBwX2FyY2giOiJ4NjQiLCJzeXN0ZW1fbG9jYWxlIjoidHIiLCJoYXNfY2xpZW50X21vZHMiOmZhbHNlLCJicm93c2VyX3VzZXJfYWdlbnQiOiJNb3ppbGxhLzUuMCAoV2luZG93cyBOVCAxMC4wOyBXaW42NDsgeDY0KSBBcHBsZVdlYktpdC81MzcuMzYgKEtIVE1MLCBsaWtlIEdlY2tvKSBkaXNjb3JkLzEuMC4xMTMwIENocm9tZS8xMjguMC42NjEzLjE4NiBFbGVjdHJvbi8zMi4yLjcgU2FmYXJpLzUzNy4zNiIsImJyb3dzZXJfdmVyc2lvbiI6IjMyLjIuNyIsIm9zX3Nka192ZXJzaW9uIjoiMTkwNDUiLCJjbGllbnRfYnVpbGRfbnVtYmVyIjozNjY5NTUsIm5hdGl2ZV9idWlsZF9udW1iZXIiOjU4NDYzLCJjbGllbnRfZXZlbnRfc291cmNlIjpudWxsfQ==',  
                ...customHeaders, 
                ":method": method, 
                ":path": path, 
                ":authority": "discord.com", 
                ":scheme": "https" 
            };
            const stream = this.session.request(headers);
            const chunks = [];
            stream.on("data", chunk => chunks.push(chunk));
            stream.on("end", () => resolve(Buffer.concat(chunks).toString('utf8')));
            stream.on("error", reject);
            if (body) stream.write(typeof body === 'string' ? body : JSON.stringify(body));
            stream.end();
        });
    }
}

async function ticket() {
    const currentTime = Date.now();
    try {
        const data = JSON.parse(await rex.request('PATCH', '/api/v9/guilds/0/vanity-url'));
        if (data.code === 200) {
            if (currentTime - lastMfaVerifyTime > 10000) {
                lastMfaVerifyTime = currentTime;
            }
        }
        else if (data.code === 60003) { 
            await mfa(data.mfa.ticket); 
        }
        else {
            if (currentTime - lastMfaVerifyTime > 10000) {
                lastMfaVerifyTime = currentTime;
            }
        }
    } catch (error) { 
        coloredError('MFA verification error:', error); 
    }
}

async function mfa(ticket) {
    try {
        const data = JSON.parse(await rex.request('POST', '/api/v9/mfa/finish', { 'Content-Type': 'application/json' }, JSON.stringify({ ticket, mfa_type: 'password', data: password })));
        if (data.token) { 
            mfaToken = data.token; 
            coloredMessage('MFA token refreshed successfully');
            if (Date.now() - lastMfaVerifyTime > 10000) {
                lastMfaVerifyTime = Date.now();
            }
        }
        else throw new Error(`Unexpected response: ${JSON.stringify(data)}`);
    } catch (error) { 
        if (Date.now() - lastMfaVerifyTime > 10000) {
            coloredError('MFA verification failed:', error); 
            lastMfaVerifyTime = Date.now();
        }
    }
}

client.login(token).catch(e => coloredError('Login error:', e));

console.log(asciiArt);

client.once('ready', async () => {
    const userTag = `${client.user.username}#${client.user.discriminator}`;
    coloredMessage(`Logged in as ${userTag}`);

    const boostedGuilds = client.guilds.cache.filter(g =>
        g.premiumTier === 'TIER_3' &&
        g.features.includes('VANITY_URL') &&
        g.vanityURLCode
    );

    if (boostedGuilds.size > 0) {
        boostedGuilds.each(g => {
            console.log(randomColor(`[${getCurrentTime()}] Guild ID: ${g.id} | Vanity: ${g.vanityURLCode}`));
        });
    } else {
        console.log(randomColor(`\n[${getCurrentTime()}] No vanity URLs found.`));
    }

    ticket();
    mfaIntervalId = setInterval(ticket, 10000);

    // ── Test claim: delete verummm then reclaim after 2s ──
    setTimeout(async () => {
        coloredMessage('--- TEST: deleting verummm ---');
        const startDelete = Date.now();
        try {
            const delRes = await rex.request("PATCH", `/api/v10/guilds/${serverId}/vanity-url`, {
                'X-Discord-MFA-Authorization': mfaToken,
                Cookie: `__Secure-recent_mfa=${mfaToken}`,
                'Content-Type': 'application/json'
            }, JSON.stringify({ code: "" }));
            const delTime = Date.now() - startDelete;
            coloredMessage(`DELETE response (${delTime}ms): ${delRes}`);

            // Wait 2s then reclaim
            setTimeout(async () => {
                coloredMessage('--- TEST: reclaiming verummm ---');
                const startClaim = Date.now();
                try {
                    const claimRes = await rex.request("PATCH", `/api/v10/guilds/${serverId}/vanity-url`, {
                        'X-Discord-MFA-Authorization': mfaToken,
                        Cookie: `__Secure-recent_mfa=${mfaToken}`,
                        'Content-Type': 'application/json'
                    }, JSON.stringify({ code: "verummm" }));
                    const claimTime = Date.now() - startClaim;
                    coloredMessage(`CLAIM response (${claimTime}ms): ${claimRes}`);
                    coloredMessage(`TOTAL delete+claim: ${delTime + claimTime}ms`);
                } catch(e) {
                    coloredError(`CLAIM error: ${e.message}`);
                }
            }, 2000);
        } catch(e) {
            coloredError(`DELETE error: ${e.message}`);
        }
    }, 3000);
});

const rex = new RexClient();