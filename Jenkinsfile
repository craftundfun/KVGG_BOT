pipeline {
    agent any
    stages {
         stage('Deploy') {
             steps {
                 script {
                     sshagent(credentials : ['root-strato']) {
                        sh 'ssh root@axellotl.de "cd /home/axellotl/web/DiscordBot/KVGG_BOT/ && ./deploy.sh"'
                    }
                 }
             }
         }
     }
}
