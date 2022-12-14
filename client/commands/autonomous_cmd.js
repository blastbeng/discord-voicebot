const { SlashCommandBuilder } = require('@discordjs/builders');
require( 'console-stamp' )( console );
const fs = require('fs');
const config = require("../config.json");
const fetch = require('node-fetch');

const path = config.CACHE_DIR;
const api=config.API_URL;
const text="&text=";
const path_text=config.API_PATH_TEXT

module.exports = {
    data: new SlashCommandBuilder()
        .setName('autonomous')
        .setDescription("Abilita o Disabilita il bot ad ascoltare tutto e rispondere a 'tono'")
        .addBooleanOption(option => option.setName('bool').setDescription('True o False').setRequired(true)),
    async execute(interaction) {
        
        if (!interaction.member._roles.includes(config.ENABLED_ROLE)){
            interaction.reply({ content: "Non sei abilitato all'utilizzo di questo bot.", ephemeral: true });
        } else {
            const bool = interaction.options.getBoolean('bool');
            if(bool){
                config.ENABLED=true;
                config.AUTONOMOUS=true;
                interaction.reply({ content: "Il bot ora risponder√† a qualsiasi attivazione vocale.", ephemeral: true });
            } else {
                config.ENABLED=true;
                config.AUTONOMOUS=false;
                interaction.reply({ content: "Il pezzente ora risponder√† solo se interpellato con 'scemo', 'pezzente' o 'bot'.", ephemeral: true });
            }
        }
    }
}; 
