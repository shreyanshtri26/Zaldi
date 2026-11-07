# Admin guide

For the person who runs a shop on Zaldi (the **store owner**) and the person who runs the server (the **server admin**). No code is needed
for anything here.

## 1. Signing in

Go to `/admin`. There are three tabs:

-   **Sign in** — your own email and password (store owners and viewers). If you turned on two-step sign-in, you then type the 6-digit
    code from your authenticator app (or a recovery code). **Forgot your password?** sends a reset link by email when the server is set up
    to send email; otherwise ask your server admin for a link (section 6).
-   **Create a store** — makes a new shop and makes you its owner. Only appears to work when the server allows sign-up (`ALLOW_SIGNUP=1`).
-   **Server admin** — the server's admin password (see section 8).

A reset link opens this same page with a form to choose a new password.

Roles: an **owner** can change everything in their store; a **viewer** can look but not change anything. Tokens last 12 hours.

## 2. Setting up a new shop: the order that works

1. **Content -> Store connection:** say where your products live and press **Test connection** (see [CONNECTORS.md](CONNECTORS.md)).
2. **Policies:** write your returns, shipping and payment policies. The assistant quotes them.
3. **Content -> AI model:** optionally use your own Gemini or Groq key and pick a model (section 4).
4. **Content -> Storefront:** your brand name, colours, greeting and quick actions.
5. **Content -> Add to your website:** copy the line into your site and list the websites allowed to show it.
6. **Chats / Metrics:** after launch, watch what shoppers ask and how the assistant does.

## 3. The pages

| Page | What you do there |
|---|---|
| **Overview** | See counts of products, policies, chats and low-stock items |
| **Products** | Add, edit, delete; upload a photo; table and grid views; filter and sort. (Built-in store only) |
| **Policies** | The text the assistant uses to answer policy questions. Editing re-indexes it at once |
| **Chats** | Every conversation, with the tools the assistant used for each answer |
| **Metrics** | Speed (median and slowest 5%), cost per answer, tokens, tool failures, answer-check counts, thumbs up/down by prompt version |
| **Content -> Storefront** | Greeting, heading, brand name, colours, layout, hidden categories, quick-action cards |
| **Content -> Assistant** | The assistant's prompts, and **Experiment: variant B** to test a second wording on half the shoppers |
| **Content -> Store connection** | Which shop the assistant searches, its keys, and the Test checklist |
| **Content -> AI model** | Provider, your API keys, and the model (section 4) |
| **Content -> Add to your website** | The embed line and the allowed websites |
| **Content -> Account** | Change your own password |
| **Server** | Server admin only: admin password and database (sections 8 and 9) |

Everything starts from built-in defaults. Clear a value or choose **Reset to default** to go back.

## 4. AI model: your own key and model

**Content -> AI model** controls which AI answers your shoppers and who pays for it.

-   **Provider for chats:** Gemini (Google) or Groq. *Automatic* uses the provider you have your own key for, or the server's default.
-   **Your API key:** paste a key from [Google AI Studio](https://aistudio.google.com/apikey) (starts with `AIza`) or the
    [Groq console](https://console.groq.com) (starts with `gsk_`). It is encrypted, used only for your store, and never shown again (only its
    last four characters). **Test key** makes one tiny request and tells you in plain words what happened: it works, the quota is used up,
    or the provider did not accept it. **Remove my key** returns you to the server's key.
-   **Model:** a dropdown of the chat models the provider currently offers for your key, newest first, straight from the provider, so it
    stays up to date. **Refresh list** asks again. **Use the default model** resets it. Without a key you see a built-in list.
-   Photo search and similarity search use Gemini. A store with its own Gemini key gets real embeddings even if the server has none.

## 5. Add the assistant to your website

Copy the line shown in **Add to your website** into your site's pages, just before `</body>`:

``` html
<script src="https://YOUR-ZALDI-HOST/widget.js" data-store="your-store-id" async></script>
```

List your website(s) under **Websites allowed to show the assistant**, for example `https://myshop.com, https://www.myshop.com`. Until you
add one, your assistant will not appear anywhere. Your site can also tell the assistant what the shopper is looking at and hear what they
add in the chat; see the README ("Add the assistant to your website").

## 6. Managing stores and accounts (server admin)

The **Stores** page (only the server admin sees it):

-   **New store:** a name and an id (3 to 32 lowercase letters, digits or dashes; it goes in the website snippet). It starts empty, as a draft.
-   **Draft / Live** for each store, and **Delete** (you must type the store's id; it erases all of the store's data and cannot be undone).
-   **Accounts** for each store: add an owner or viewer with an email and a starting password, change someone's role (they have to sign in
    again), delete an account, **Reset link** (a one-hour, single-use link you send to the person, for a forgotten password), and
    **Turn off two-step** (for a lost phone; the owner can turn it on again).

Sending a reset link by email needs `SMTP_HOST` and `SMTP_FROM` on the server; without them people ask you for a link.

## 7. Your password

Store owners: **Content -> Account**.

-   **Your password:** the current password and a new one (at least 10 characters). Changing it signs out your other devices.
-   **Two-step sign-in:** adds a code from your phone after the password, so a stolen password alone is not enough. Enter your password,
    add the shown key to an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password, Authy...), type the 6-digit code
    it shows, and **save the 8 recovery codes** (each works once and they are never shown again). To turn it off you need your password and
    a current code. Five wrong attempts lock the account for ten minutes.

## 8. Server admin password

**Server -> Admin password.** The server's credential is normally the `ADMIN_TOKEN` setting on the host. Set a password of your own here
(at least 12 characters) and you never need to edit the host's settings again. The `ADMIN_TOKEN` keeps working as a **recovery key** if
you forget the password; remove it from the host's settings when you want only the portal password to work. "Go back to the environment
token" removes the portal password.

## 9. Database (server admin)

**Server -> Database** shows what the server runs on (SQLite files or Postgres) and lets you move to Postgres, for example Neon, without
touching the host's settings:

1. Paste the Postgres address (for Neon, the *pooled* connection string) and press **Test connection**. It checks the address, the login
   and that pgvector is available, and tells you whether the database is empty. The address is never shown again.
2. **Copy my data** copies every store from this server's SQLite files into that database. Your files here are not changed. If the
   database already has Zaldi data you must tick *Erase what is in that database and replace it* and type `REPLACE`.
3. **Save and use after restart** stores the address (encrypted on the server's disk). Then **Restart now** (type `RESTART`): on a hosted
   server it restarts by itself; on your own computer it stops and you start it again.

If the host also sets `DATABASE_URL`, that wins; the page tells you. **Remove the saved address** returns to SQLite.

## 10. Troubleshooting

| You see | Do this |
|---|---|
| "Test connection" fails with a fix | Follow the fix shown next to the failed check |
| "The key is valid, but its quota is used up" | Wait for the daily reset, enable billing with the provider, or use another key |
| The assistant does not appear on your site | Add the site under Allowed websites, and check the `data-store` id |
| A model is missing from the dropdown | Press **Refresh list**; models your key cannot use are not listed |
| You forgot the server admin password | Use the `ADMIN_TOKEN` from the host's settings, then set a new password |
| An owner forgot their password | Press *Reset link* on the Stores page and send it to them, or let them use *Forgot your password?* if the server can send email |
| An owner lost their phone | Use a recovery code, or press *Turn off two-step* on the Stores page |
