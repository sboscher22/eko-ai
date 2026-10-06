const form = document.getElementById("chat-form");
const input = document.getElementById("message");
const chat = document.getElementById("chat");

function ajouterMessage(texte, type) {
    const message = document.createElement("div");

    message.className = `message ${type}`;
    message.textContent = texte;

    chat.appendChild(message);

    // Faire défiler automatiquement vers le bas
    chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const texte = input.value.trim();

    if (!texte) {
        return;
    }

    // Afficher le message de l'utilisateur
    ajouterMessage(texte, "user");

    // Vider la zone de texte
    input.value = "";

    try {
        const reponse = await fetch("http://127.0.0.1:8000/chat", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: texte
            })
        });

        const donnees = await reponse.json();

        // Afficher la réponse d'Eko
        ajouterMessage(donnees.response, "eko");

    } catch (erreur) {
        ajouterMessage(
            "Impossible de contacter le serveur Eko.",
            "eko"
        );

        console.error(erreur);
    }
});
