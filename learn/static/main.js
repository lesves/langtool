const query = `
query getTasks($id: ID!, $num_queue: Int = 10, $num_new: Int = 0) {
  course(id: $id) {
    queue: reviewQueue(n: $num_queue) {
      task {
        ...Exercise
      }
    }
    new(n: $num_new) {
      ...Exercise
    }
  }
}

fragment Exercise on Task {
  id
  html
  correct

  sentence {
    text
    translations {
      text
    }
  }
}

mutation attemptTask($id: ID!, $success: Boolean!) {
  attempt(id: $id, success: $success) {
    lastReview
    nextReview
  }
}
`;


function api_call(operation, variables) {
  return fetch("/graphql/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          operationName: operation,
          query: query,
          variables: variables
        })
      });
}


const app = {
  tasks: [],
  main: null,

  state: "loading",
  field: null,

  speech: new SpeechSynthesisUtterance(),

  get current() {
    return app.tasks[0];
  },

  view() {
    app.main.querySelector(".sentence").innerHTML = app.current.html;
    app.field = app.main.querySelector("input");
    app.field.addEventListener("input", app.input);

    const ul = app.main.querySelector(".translations");
    ul.innerHTML = "";
    for (let t of app.current.sentence.translations) {
      let li = document.createElement("li");
      li.innerText = t.text;
      ul.appendChild(li);
    }
    app.field.focus();

    app.state = "task";
  },

  action() {
    if (app.state === "submitted") {
      app.next();
    } else if (app.state === "task") {
      app.attempt();
    }
  },

  attempt() {
    let success = app.validate(app.field.value).success;

    api_call("attemptTask", {
      "id": app.current.id, 
      "success": success,
    });

    if (success) {
      app.field.style.color = "black";
    } else {
      app.field.style.color = "red";
    }
    app.field.value = app.current.correct;
    app.field.setAttribute("readonly", "");

    app.speech.text = app.current.sentence.text;
    app.speech.lang = config.lang;
    speechSynthesis.speak(app.speech);
    speechSynthesis.resume();

    app.state = "submitted";
  },

  next() {
    app.tasks.shift();
    app.view();
    speechSynthesis.cancel();

    if (app.tasks.length <= 5) {
      app.load();
    }
  },

  validate(value) {
    const correct = app.current.correct.toLowerCase();
    const entered = value.toLowerCase();

    let res = {"success": false, "prefix": false}

    if (correct.startsWith(entered)) {
      res.prefix = true;
    }
    if (correct === entered) {
      res.success = true;
    }
    return res;
  },

  input(event) {
    const res = app.validate(event.target.value);

    if (res.prefix) {
      event.target.style.color = "green";
    } else {
      event.target.style.color = "red";
    }

    if (res.success) {
      app.attempt();
    }
  },

  load() {
    return api_call("getTasks", {
            id: config.course,
            num_queue: 10,
            num_new: 5
          }).then(res => res.json()).then(res => {
      app.tasks.push(...res.data.course.queue
        .map(x => x.task)
        .filter(x => !app.tasks.includes(x)));
      app.tasks.push(...res.data.course.new);
    });
  },

  setup() {
    app.main = document.querySelector("main");
    app.load().then(app.view);

    window.addEventListener("keypress", function(event) {
      if (event.key === "Enter") {
        app.action();
      }
    });

    document.querySelector(".next").addEventListener("click", app.action);
  }
}


window.addEventListener("load", app.setup);

window.speechSynthesis.addEventListener("voiceschanged", () => {
  const voices = speechSynthesis.getVoices().filter((voice) => voice.lang.startsWith(config.lang));
  if (voices.length > 0) {
    app.speech.voice = voices[0];

    const select = document.getElementById("voice");
    for (let i = 0; i < voices.length; i++) {
      let opt = document.createElement("option");
      opt.innerText = voices[i].name;
      opt.value = i;
      select.appendChild(opt);
    }

    select.addEventListener("change", (event) => {
      app.speech.voice = voices[event.target.value];
    });
  }
});
