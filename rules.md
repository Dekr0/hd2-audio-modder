## Constraint & Requirement

- When an user input appear, it will trigger an action.
- If an action is short (e.g. Change a True / False flag, set / unset a value 
without other operations, etc), perform this action inline / inside the rendering
 loop.
- Otherwise, delay the execution of this action until the current cycle of the 
rendering loop is finish. 
- By finishing means the content that will be displayed on the screen is already 
computed, and the content is draw on the screen.
- An action can trigger another action. The execution constraint of this action 
must follow the same constraint specified above.
- There are three ways of delaying actions.

### Event Action

- The execution order of actions must be maintained. 
- The execution order of actions must be same as the order of which actions are 
acted from user inputs.
- The order of which the execution of actions finish must match up as well.
- For action chaining, the next action must execute right after the previous 
action that trigger it.

#### Example

- The order of which user inputs occur:
    - User Input A -> Action A
    - User Input B -> Action B -> Action D
    - User Input C -> Action C
- The execution order and the order of which actions finish
    - Execute Action A -> Action A finish
    - Execute Action B -> Action B finish
    - Execute Action D -> Action D finish
    - Execute Action C -> Action C finish

### Asynchronous Action

- If an action take a long time to finish, this action should execute
asynchronously instead of executing in the event / callback bus.
- For asynchronous actions, the execution order must be maintained.
- The execution order must be same as the order of which actions are acted from 
user inputs.
- For single thread asynchronous action, the order which actions finish must be 
maintained.
- For multi threading asynchronous action, the order which actions finish will 
be difference.
- For action chaining, 
    - the next action of a single thread asynchronous action executes right after 
    the previous single thread asynchronous action that trigger it.

### Priority on the usage of action 

1. Event / Callback bus 
2. Single thread asynchronous action (Concurrent)
    - Divide a long running action into multiple small actions
    - Execute some amount of those actions in between rendering loop
3. Multi thread asynchronous action (Parallelism)
    - Use this only when:
        - an action does not mutate any state in the application, or it's fire 
        and forget, or
        - an action does mutate state but this action is divided into two stages. 
            - The first stage does not mutate any state. This can be put into a 
            different thread.
            - The second stage is collect the result of first stage, and mutate 
            state.
            - The second stage must in the form of an action. This action must 
            be delayed as well.
4. Inline actions should only cause minor visual changes. They shouldn't have 
any side effect that conflict with other actions that execute outside of the
 rendering loop.

### Cancellation and Exception

- Whenever a cancellation and an exception appear on an action, all subsequent 
action will be canceled / rejected.

### Action Policies

- Exception and cancellation of all actions must be short. Don't block the loop!!!
- For micro action, since they're execute in the main thread, make sure they don't 
consume too much time. Otherwise it will block the loop.
    - Divide a long action into multiple micro action

### Consequence

- Inline actions will always have the highest priority. If an inline action has 
side effect that conflict with another delayed action (synchronous or 
asynchronous), the execution order of these two actions matter.

## Architecture

### Goal

- This architecture should achieve the following:
    - State mutation and data flow for both delayed synchronous and asynchronous 
    execution can be reason and predict without difficulties.
    - Asynchronous execution can be controlled and tracked.
        - Cancellation
        - Get the actor

### Implementation

- Each action must have the following states:
    - pending,
    - result (finish without rejection and cancellation),
    - reject (exception),
    - cancel
- Actions and actors must maintain the following relationship
    - each action must contain the actor, 
    - and each actor must maintain a copy of the action.
- In order to run an action, it needs to be scheduled. By scheduling means pushing 
into a queue.

#### Cancellation and Rejection

- When canceling an action, the actor mark the copy of its action. The actor 
don't cancel it explicitly.
    - Only cancel an action explicitly if it's urgent.
- The event loop will cancel / ignore those action. 

#### Event / Callback Bus

- Event / callback bus capture simple delayed action.
- It's a FIFO queue.
- In between each frame, execute all actions in FIFO order.
- If an event will trigger another action (event), push it in the head of the 
queue.

#### Micro Task Queue

- It's a FIFO queue
- In between each frame, execute X amount of actions in FIFO order.
- If a micro action has another micro action, push it in the head of the queue.

#### Thread Task Queue.

- It's a FIFO queue.
- In between each frame, dispatch all actions in FIFO order, and collect the 
result of done actions.
- If an action has a second stage, this second stage must be in the form a micro 
action.
