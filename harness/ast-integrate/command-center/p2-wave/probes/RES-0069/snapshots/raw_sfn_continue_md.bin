

# Continue long-running workflows using Step Functions API (recommended)
<a name="tutorial-continue-new"></a>

AWS Step Functions is designed to run workflows with a finite duration and number of steps. Standard workflow executions have a maximum duration of one year and 25,000 events (see [Step Functions service quotas](service-quotas.md)).

For long-running executions, you can avoid reaching the hard quota by starting a new workflow execution from the `Task` state. You need to break your workflows up into smaller state machines which continue ongoing work in a new execution.

To start new workflow executions, you will call the `StartExecution` API action from your `Task` state and pass the necessary parameters.

Step Functions can start workflow executions by calling its own API as an [integrated service](integrate-services.md). We recommend that you use this approach to avoid exceeding service quotas for long-running executions.

## Step 1: Create a long-running state machine
<a name="use-sfn-api-create-called-state-machine"></a>

Create a long-running state machine that you want to start from the `Task` state of a different state machine. For this tutorial, use the [state machine that uses a Lambda function](tutorial-creating-lambda-state-machine.md).

**Note**  
Make sure to copy the name and Amazon Resource Name of this state machine in a text file for later use.

## Step 2: Create a state machine to call the Step Functions API action
<a name="use-sfn-api-create-caller-state-machine"></a>

**To start workflow executions from a `Task` state**

1. Open the [Step Functions console](https://console.aws.amazon.com/states/home), choose **State machines** from the menu, then choose **Create state machine**.

1. Choose **Create from blank**.

1. Name your state machine, then choose **Continue** to edit your state machine in Workflow Studio.

1. From the **Actions** tab, drag the **StartExecution** API action and drop it on the empty state labelled **Drag first state here**.

1. Choose the **StartExecution** state and do the following in the **Configuration** tab in [Design mode](workflow-studio.md#wfs-interface-design-mode):

   1. Rename the state to **Start nested execution**.

   1. For **Integration type**, choose **AWS SDK - new** from the dropdown list.

   1. In **API Parameters**, do the following:

      1. For `StateMachineArn`, replace the sample Amazon Resource Name with the ARN of your state machine. For example, enter the ARN of the [state machine that uses Lambda](tutorial-creating-lambda-state-machine.md).

      1. For `Input` node, replace the existing placeholder text with the following value:

         ```
         "Comment": "Starting workflow execution using a Step Functions API action"
         ```

      1. Make sure your inputs in **API Parameters** look similar to the following:

         ```
         {
           "StateMachineArn": "arn:aws:states:us-east-2:123456789012:stateMachine:{{LambdaStateMachine}}",
           "Input": {
             "Comment": "Starting workflow execution using a Step Functions API action",
             "AWS_STEP_FUNCTIONS_STARTED_BY_EXECUTION_ID.$": "$$.Execution.Id"
           }
         ```

1. (Optional) Choose **Definition** on the [Inspector panel](workflow-studio.md#workflow-studio-components-formdefinition) panel to view the automatically-generated [Amazon States Language](concepts-amazon-states-language.md) (ASL) definition of your workflow.
**Tip**  
You can also view the ASL definition in the [Code editor](workflow-studio.md#wfs-interface-code-editor) of Workflow Studio. In the code editor, you can also edit the ASL definition of your workflow.

1. Specify a name for your state machine. To do this, choose the edit icon next to the default state machine name of **MyStateMachine**. Then, in **State machine configuration**, specify a name in the **State machine name** box.

   For this tutorial, enter the name **ParentStateMachine**.

1. (Optional) In **State machine configuration**, specify other workflow settings, such as state machine type and its execution role.

   For this tutorial, keep all the default selections in **State machine settings**.

   If you've [previously created an IAM role](procedure-create-iam-role.md) with the correct permissions for your state machine and want to use it, in **Permissions**, select **Choose an existing role**, and then select a role from the list. Or select **Enter a role ARN** and then provide an ARN for that IAM role.

1. In the **Confirm role creation** dialog box, choose **Confirm** to continue.

   You can also choose **View role settings** to go back to **State machine configuration**.
**Note**  
If you delete the IAM role that Step Functions creates, Step Functions can't recreate it later. Similarly, if you modify the role (for example, by removing Step Functions from the principals in the IAM policy), Step Functions can't restore its original settings later. 

## Step 3: Update the IAM policy
<a name="use-sfn-api-update-policy-start-execution"></a>

To make sure your state machine has permissions to start the execution of the [state machine that uses a Lambda function](tutorial-creating-lambda-state-machine.md), you need to attach an inline policy to your state machine's IAM role. For more information, see [Embedding Inline Policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_manage-attach-detach.html#embed-inline-policy-console) in the *IAM User Guide*.

1. On the **ParentStateMachine** page, choose the **IAM role ARN** to navigate to the IAM **Roles** page for your state machine.

1. Assign an appropriate permission to the IAM role of the **ParentStateMachine** for it to be able to start execution of another state machine. To assign the permission, do the following:

   1. On the IAM **Roles** page, choose **Add permissions**, and then choose **Create inline policy**.

   1. On the **Create policy** page, choose the **JSON** tab.

   1. Replace the existing text with the following policy.  
****  

      ```
      {
        "Version":"2012-10-17",		 	 	 
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "states:StartExecution"
                ],
                "Resource": [
                    "arn:aws:states:{{us-east-1}}:{{123456789012}}:stateMachine:{{LambdaStateMachine}}"
                ]
            }
        ]
      }
      ```

   1. Choose **Review policy**.

   1. Specify a name for the policy, and then choose **Create policy**.

## Step 4: Run the state machine
<a name="use-sfn-api-start-execution"></a>

State machine executions are instances where you run your workflow to perform tasks.

1. On the **ParentStateMachine** page, choose **Start execution**.

   The **Start execution** dialog box is displayed.

1. In the **Start execution** dialog box, do the following:

   1. (Optional) Enter a custom execution name to override the generated default.
**Non-ASCII names and logging**  
Step Functions accepts names for state machines, executions, activities, and labels that contain non-ASCII characters. Because such characters will prevent Amazon CloudWatch from logging data, we recommend using only ASCII characters so you can track Step Functions metrics.

   1. (Optional) In the **Input** box, enter input values in JSON format to run your workflow.

   1. Choose **Start execution**.

   1. The Step Functions console directs you to a page that's titled with your execution ID. This page is known as the *Execution Details* page. On this page, you can review the execution results as the execution progresses or after it's complete.

      To review the execution results, choose individual states on the **Graph view**, and then choose the individual tabs on the [Step details](concepts-view-execution-details.md#exec-details-intf-step-details) pane to view each state's details including input, output, and definition respectively. For details about the execution information you can view on the *Execution Details* page, see [Execution details overview](concepts-view-execution-details.md#exec-details-interface-overview).

1. Open the **LambdaStateMachine** page and notice a new execution triggered by the **ParentStateMachine**.