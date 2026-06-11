# 🚨 BUG #1: Python/SQL Injection Vector
# This directly concatenates user input into a SQL query, making it highly vulnerable to a destructive database attack.
def get_user_profile(user_input_id):
    query = "SELECT * FROM users WHERE id = '" + user_input_id + "';"
    print(f"Executing unsafe query: {query}")
    return query


# 🚨 BUG #2: Infinite JavaScript Loop Trap (Written as a comment/string sample)
# If this logic executes, the condition `i >= 0` will always stay true, freezing the user's browser or locking the server CPU.
broken_js_loop = """
function clearUserSession() {
    let users = ["Alice", "Bob", "Charlie"];
    for (let i = 0; i < users.length; i++) {
        console.log("Processing: " + users[i]);
        i--; // Fatal flaw: Decrementing inside an increment loop keeps 'i' trapped at 0 or below!
    }
}
"""


# 🚨 BUG #3: Faulty React Lifecycle / State Hook Loop
# Calling `setUserData` directly inside the body of a functional component triggers an infinite re-render loop that crashes React.
broken_react_component = """
import React, { useState } from 'react';

export function UserDashboard() {
    const [userData, setUserData] = useState({ loggedIn: true });
    
    // Fatal flaw: Setting state directly in the render path triggers infinite loops.
    setUserData({ loggedIn: true }); 
    
    return <div>Dashboard Active</div>;
}
"""